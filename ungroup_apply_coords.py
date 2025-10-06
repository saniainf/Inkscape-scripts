# -*- coding: utf-8 -*-
"""Inkscape extension: Ungroup text groups and bake transforms into coordinates.

Основная задача: найти группы <g>, содержащие единственный элемент <text> (и/или его вложенные tspan),
перенести сам <text> на уровень выше, применив матрицу трансформации группы к:
  * координатам атрибутов x / y у <text>
  * координатам внутри атрибутов x / y tspans (если заданы)
  * трансформации scale(1,-1) внутри текста — объединить с общей матрицей
и удалить исходную группу, если она становится пустой.

Ограничения / Упрощения:
  * Не обрабатываем сложные случаи, где в группе более одного графического элемента.
  * Если в <text> есть transform, он композиционно умножается.
  * Матрицы компонуются в порядке: M_group * M_text.
  * Параметр only_single_text управляет тем, обрабатывать ли только группы с ровно одним <text>.

"""
import inkex
from inkex.transforms import Transform

class UngroupApplyCoords(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument('--only_single_text', type=inkex.Boolean, default=True,
                          help='Обрабатывать только группы с единственным <text>')
        pars.add_argument('--apply_to_tspan', type=inkex.Boolean, default=True,
                          help='Применять трансформацию к координатам tspan (x/y списки)')

    def effect(self):
        processed = 0
        skipped = 0

        def local_name(el):
            return el.tag.split('}',1)[-1]

        # Собираем кандидатов: группы с transform и текстом
        for g in list(self.svg.xpath('//svg:g', namespaces=inkex.NSS)):
            # Пропустим, если нет transform
            if 'transform' not in g.attrib:
                continue
            children = [c for c in g if local_name(c) != 'desc' and local_name(c) != 'title']
            text_children = [c for c in children if local_name(c) == 'text']
            if not text_children:
                continue
            if self.options.only_single_text and (len(children) != 1 or len(text_children) != 1):
                skipped += 1
                continue
            # Берём первый текст
            text_el = text_children[0]
            try:
                M_group = Transform(g.attrib.get('transform'))
            except Exception:
                self.msg(f"Пропущена группа (некорректный transform): id={g.attrib.get('id')}")
                skipped += 1
                continue
            # Матрица текста
            try:
                M_text = Transform(text_el.attrib.get('transform')) if 'transform' in text_el.attrib else Transform()
            except Exception:
                M_text = Transform()
            # Общая матрица
            M_total = M_group * M_text

            # Применяем матрицу к координатам <text>
            def parse_float_list(val):
                parts = [p for p in val.replace(',', ' ').split() if p]
                res = []
                for p in parts:
                    try:
                        res.append(float(p))
                    except Exception:
                        pass
                return res

            def apply_to_xy(el):
                # Применяем только если есть и x и y (иначе Inkscape сам решит позиционирование)
                xs = parse_float_list(el.attrib.get('x', '')) if 'x' in el.attrib else []
                ys = parse_float_list(el.attrib.get('y', '')) if 'y' in el.attrib else []
                # Дополняем короткий список последним значением, если длины не совпадают
                if xs and ys and len(xs) != len(ys):
                    if len(xs) < len(ys):
                        xs += [xs[-1]] * (len(ys) - len(xs))
                    else:
                        ys += [ys[-1]] * (len(xs) - len(ys))
                if not xs:
                    # Пустой x -> возьмём 0
                    xs = [0.0]
                if not ys:
                    ys = [0.0] * len(xs)
                new_xs = []
                new_ys = []
                for xx, yy in zip(xs, ys):
                    # Применяем матрицу
                    nx, ny = M_total.apply_to_point([xx, yy])
                    new_xs.append(nx)
                    new_ys.append(ny)
                # Записываем обратно
                el.attrib['x'] = ' '.join(f"{v:.6g}" for v in new_xs)
                el.attrib['y'] = ' '.join(f"{v:.6g}" for v in new_ys)

            apply_to_xy(text_el)

            if self.options.apply_to_tspan:
                for node in text_el.iter():
                    if node is text_el:
                        continue
                    if local_name(node) == 'tspan':
                        apply_to_xy(node)

            # Удаляем transform у текста, он теперь в координатах
            if 'transform' in text_el.attrib:
                del text_el.attrib['transform']
            # Удаляем transform у группы
            del g.attrib['transform']

            # Переносим текст выше группы
            parent = g.getparent()
            if parent is None:
                skipped += 1
                continue
            parent.insert(parent.index(g), text_el)
            # Если в группе остались только desc/title или вообще пусто — удаляем
            residual = [c for c in g if local_name(c) not in ('desc','title')]
            if not residual:
                parent.remove(g)
            processed += 1
            self.msg(f"Разгруппировано: group id={g.attrib.get('id')} -> text id={text_el.attrib.get('id')}")

        self.msg(f"Итого разгруппировано групп: {processed}; пропущено: {skipped}")

if __name__ == '__main__':
    UngroupApplyCoords().run()
