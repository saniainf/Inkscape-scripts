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

    def effect(self):
        removed_count = 0

        # Собираем CSS классы из <style> (простая поддержка .class { prop:val; })
        css_map = {}
        for style_el in self.svg.xpath('//svg:style', namespaces=inkex.NSS):
            css_text = style_el.text or ''
            for selector, body in re.findall(r'(\.[\w\-]+)\s*\{([^}]+)\}', css_text):
                props = {}
                for item in body.split(';'):
                    if ':' in item:
                        k, v = item.split(':', 1)
                        props[k.strip()] = v.strip()
                css_map[selector.lstrip('.')] = props

        def get_style_value(el, prop):
            """Возвращает значение свойства с учётом: inline style, прямого атрибута, класса, наследования."""
            current = el
            while current is not None:
                # inline style
                style_attr = current.attrib.get('style', '')
                style_dict = {}
                if style_attr:
                    for item in style_attr.split(';'):
                        if ':' in item:
                            k, v = item.split(':', 1)
                            style_dict[k.strip()] = v.strip()

                if prop in style_dict:
                    return style_dict[prop]
                if prop in current.attrib:
                    return current.attrib.get(prop)

                class_attr = current.attrib.get('class', '')
                for cls in class_attr.split():
                    if cls in css_map and prop in css_map[cls]:
                        return css_map[cls][prop]

                current = current.getparent()
            return None

        def is_no_color(el):
            fill = get_style_value(el, 'fill')
            stroke = get_style_value(el, 'stroke')
            def empty(v):
                return v is None or v == '' or v.lower() == 'none'
            return empty(fill) and empty(stroke)

        def has_markers(el):
            """Проверяет наличие маркеров (arrowheads) через inline style, атрибуты или CSS класс."""
            # Прямые атрибуты marker-*
            if any(k.startswith('marker-') and 'url(' in v for k, v in el.attrib.items()):
                return True
            # Inline style
            style_attr = el.attrib.get('style', '')
            for part in style_attr.split(';'):
                if part.strip().startswith('marker-') and 'url(' in part:
                    return True
            # Классы -> смотрим в css_map
            class_attr = el.attrib.get('class', '')
            for cls in class_attr.split():
                props = css_map.get(cls, {})
                for k, v in props.items():
                    if k.startswith('marker-') and 'url(' in v:
                        return True
            return False

        def local_name(el):
            return el.tag.split('}', 1)[-1]

        # Сначала собираем кандидатов в post-order, чтобы удаление детей не мешало обходу.
        to_remove = []

        def traverse(el):
            name = local_name(el)
            # Если это контейнер, который нужно пропустить полностью (не трогаем и не лезем внутрь)
            if name in self.SKIP_TAGS and name != 'svg':
                return  # не спускаемся в defs/marker/... и не удаляем их содержимое
            # Спускаемся в детей (кроме пропущенных контейнеров)
            for child in list(el):
                traverse(child)
            if name in self.SKIP_TAGS:
                return
            if name == 'g':
                # Группа: удаляем только если она пуста или все дети будут удалены и сама без цвета.
                if is_no_color(el) and len(list(el)) == 0:
                    to_remove.append(el)
                return
            if name in self.GRAPHIC_TAGS and is_no_color(el):
                if has_markers(el):  # сохраняем линии со стрелками
                    return
                to_remove.append(el)
        # В текущей версии inkex self.svg уже является корневым элементом документа (SvgDocumentElement)
        traverse(self.svg)

        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                self.msg(f"Удалено: <{local_name(el)}> id={el.attrib.get('id', '(без id)')}")
                parent.remove(el)
                removed_count += 1

        self.msg(f"Всего удалено объектов: {removed_count}")

if __name__ == '__main__':
    RemoveNoColorObjects().run()
