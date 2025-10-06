# -*- coding: utf-8 -*-
import inkex
import re


class RemoveNoColorObjects(inkex.EffectExtension):
    """Удаляет невидимые (fill:none & stroke:none) графические элементы.

    Критерии удаления:
      * И fill, и stroke отсутствуют или равны none/''.
      * Элемент является графическим (path, rect, circle, ellipse, line, polyline, polygon, text, flowRoot, group без детей).
    Не трогаем служебные контейнеры: svg, defs, metadata, namedview, style, script, clipPath, marker, pattern, linearGradient и т.п.
    """

    GRAPHIC_TAGS = {
        'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'flowRoot', 'g'
    }
    SKIP_TAGS = {
        'svg', 'defs', 'metadata', 'namedview', 'style', 'script', 'clipPath', 'marker', 'pattern',
        'linearGradient', 'radialGradient', 'symbol'
    }

    def add_arguments(self, pars):
        pars.add_argument('--remove_empty_groups', type=inkex.Boolean, default=True, help='Удалять опустевшие группы после очистки')
        pars.add_argument('--opacity_zero_is_none', type=inkex.Boolean, default=False, help='Считать объекты с fill/stroke-opacity=0 как невидимые')
        pars.add_argument('--display_none_is_invisible', type=inkex.Boolean, default=False, help='Удалять элементы с display:none как невидимые')
        pars.add_argument('--remove_desc', type=inkex.Boolean, default=False, help='Удалять теги <desc>')
        pars.add_argument('--remove_title', type=inkex.Boolean, default=False, help='Удалять теги <title>')

    def effect(self):
        removed_count = 0

        # -------------- CSS парсинг (улучшенный) --------------
        css_map = {}
        for style_el in self.svg.xpath('//svg:style', namespaces=inkex.NSS):
            css_text = style_el.text or ''
            # Удаляем комментарии
            css_text = re.sub(r'/\*.*?\*/', '', css_text, flags=re.S)
            for block_match in re.finditer(r'([^{}]+)\{([^}]*)\}', css_text):
                selectors_raw, body = block_match.groups()
                body = body.strip()
                if not body:
                    continue
                # Разбор свойств
                props = {}
                for decl in body.split(';'):
                    if ':' in decl:
                        k, v = decl.split(':', 1)
                        props[k.strip()] = v.strip()
                # Несколько селекторов через запятую
                for sel in selectors_raw.split(','):
                    sel = sel.strip()
                    if sel.startswith('.'):
                        name = sel[1:]
                        # Мержим если класс повторяется
                        if name in css_map:
                            css_map[name].update(props)
                        else:
                            css_map[name] = dict(props)

        # -------------- Кэширование inline-стилей --------------
        style_cache = {}
        def parse_inline(el):
            if el in style_cache:
                return style_cache[el]
            d = {}
            raw = el.attrib.get('style')
            if raw:
                for item in raw.split(';'):
                    if ':' in item:
                        k, v = item.split(':', 1)
                        d[k.strip()] = v.strip()
            style_cache[el] = d
            return d

        prop_cache = {}
        def get_style_value(el, prop):
            key = (el, prop)
            if key in prop_cache:
                return prop_cache[key]
            cur = el
            while cur is not None:
                inline_dict = parse_inline(cur)
                if prop in inline_dict:
                    prop_cache[key] = inline_dict[prop]
                    return inline_dict[prop]
                if prop in cur.attrib:
                    prop_cache[key] = cur.attrib[prop]
                    return cur.attrib[prop]
                class_attr = cur.attrib.get('class', '')
                for cls in class_attr.split():
                    cls_props = css_map.get(cls, {})
                    if prop in cls_props:
                        prop_cache[key] = cls_props[prop]
                        return cls_props[prop]
                cur = cur.getparent()
            prop_cache[key] = None
            return None

        def local_name(el):
            return el.tag.split('}', 1)[-1]

        def opacity_is_zero(el):
            if not self.options.opacity_zero_is_none:
                return False
            fo = get_style_value(el, 'fill-opacity')
            so = get_style_value(el, 'stroke-opacity')
            def is_zero(v):
                try:
                    return v is not None and float(v) == 0.0
                except Exception:
                    return False
            return is_zero(fo) and is_zero(so)

        def display_none(el):
            if not self.options.display_none_is_invisible:
                return False
            disp = get_style_value(el, 'display')
            return disp is not None and disp.strip().lower() == 'none'

        def is_no_color(el):
            if display_none(el):
                return True
            fill = get_style_value(el, 'fill')
            stroke = get_style_value(el, 'stroke')
            def empty(v):
                if v is None or v == '' or v.lower() == 'none':
                    return True
                return False
            if empty(fill) and empty(stroke):
                return True or opacity_is_zero(el)  # True уже возвращает, но оставляем структуру для ясности
            # Если включена опция opacity_zero_is_none: и цвета заданы, но обе opacity == 0
            if self.options.opacity_zero_is_none and opacity_is_zero(el):
                return True
            return False

        def has_markers(el):
            # Прямые атрибуты marker-*
            if any(k.startswith('marker-') and 'url(' in v for k, v in el.attrib.items()):
                return True
            inline_dict = parse_inline(el)
            for k, v in inline_dict.items():
                if k.startswith('marker-') and 'url(' in v:
                    return True
            class_attr = el.attrib.get('class', '')
            for cls in class_attr.split():
                props = css_map.get(cls, {})
                for k, v in props.items():
                    if k.startswith('marker-') and 'url(' in v:
                        return True
            return False

        def text_has_visible_descendant(el):
            # Ищем tspan/altGlyph и пр., упрощённо только fill/stroke проверяем
            for node in el.iter():
                if node is el:
                    continue
                tag = local_name(node)
                if tag in {'tspan', 'textPath'}:
                    f = get_style_value(node, 'fill')
                    s = get_style_value(node, 'stroke')
                    if (f and f.lower() != 'none') or (s and s.lower() != 'none'):
                        return True
            return False

        to_remove = []

        def traverse(el):
            name = local_name(el)
            if name in self.SKIP_TAGS and name != 'svg':
                return
            for child in list(el):
                traverse(child)
            if name in self.SKIP_TAGS:
                return
            if name == 'g':
                if is_no_color(el) and len(list(el)) == 0:
                    to_remove.append(el)
                return
            if name == 'text':
                if is_no_color(el) and not text_has_visible_descendant(el):
                    if not has_markers(el):
                        to_remove.append(el)
                return
            if name in self.GRAPHIC_TAGS and is_no_color(el):
                if has_markers(el):
                    return
                to_remove.append(el)

        traverse(self.svg)

        # Дополнительное удаление <desc> и <title>
        removed_meta = 0
        if getattr(self.options, 'remove_desc', False):
            for d in list(self.svg.xpath('.//svg:desc', namespaces=inkex.NSS)):
                parent = d.getparent()
                if parent is not None:
                    parent.remove(d)
                    removed_meta += 1
        if getattr(self.options, 'remove_title', False):
            for t in list(self.svg.xpath('.//svg:title', namespaces=inkex.NSS)):
                parent = t.getparent()
                if parent is not None:
                    parent.remove(t)
                    removed_meta += 1

        # Удаляем первичный список графики
        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                self.msg(f"Удалено: <{local_name(el)}> id={el.attrib.get('id', '(без id)')}")
                parent.remove(el)
                removed_count += 1

        # Итеративное удаление опустевших групп
        if self.options.remove_empty_groups:
            changed = True
            while changed:
                changed = False
                for g in list(self.svg.xpath('//svg:g', namespaces=inkex.NSS)):
                    if len(list(g)) == 0 and is_no_color(g):
                        parent = g.getparent()
                        if parent is not None:
                            self.msg(f"Удалено: <g> (пустая) id={g.attrib.get('id', '(без id)')}")
                            parent.remove(g)
                            removed_count += 1
                            changed = True

        if removed_meta:
            self.msg(f"Удалено meta-тегов (desc/title): {removed_meta}")
        self.msg(f"Всего удалено объектов: {removed_count}")

if __name__ == '__main__':
    RemoveNoColorObjects().run()
