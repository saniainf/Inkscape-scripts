# Inkscape Extension: Remove No Color Objects

Удаляет из SVG объекты без заливки и обводки (fill:none и stroke:none, с учётом наследования и CSS-классов).

## Установка

1. Скопируйте файлы `remove_no_color.py` и `remove_no_color.inx` в папку расширений Inkscape.
   - Windows: `%APPDATA%\Inkscape\extensions`
   - Linux: `~/.config/inkscape/extensions/`
   - macOS: `~/Library/Application Support/org.inkscape.Inkscape/config/inkscape/extensions/`
2. Перезапустите Inkscape.
3. Откройте: Extensions → Очистка → Remove No Color Objects.

## Параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| Удалять пустые группы после очистки (`remove_empty_groups`) | Итеративно удаляет опустевшие `<g>` без цвета. | true |
| Opacity 0 => невидимо (`opacity_zero_is_none`) | Считать элемент невидимым, если и fill-opacity, и stroke-opacity равны 0. | false |
| Удалять display:none (`display_none_is_invisible`) | Удалять элементы, у которых display:none (как скрытые). | false |
| Удалять теги `<desc>` (`remove_desc`) | Удаляет все элементы `<desc>` в документе. | false |
| Удалять теги `<title>` (`remove_title`) | Удаляет все элементы `<title>` в документе. | false |

## Логика определения невидимости

Элемент считается невидимым, если выполняется одно из:
- fill отсутствует или none И stroke отсутствует или none (учитывается наследование вверх по иерархии);
- (опция) обе прозрачности (fill-opacity и stroke-opacity) = 0;
- (опция) display:none.

Не удаляются элементы, если:
- Есть маркеры (marker-start/mid/end с url(...));
- Текст (`<text>`) содержит дочерние `tspan` / `textPath` с видимым цветом.

## Что обрабатывается
Теги: path, rect, circle, ellipse, line, polyline, polygon, text, flowRoot, g.
Пропускаются контейнеры ресурсов: defs, clipPath, marker, pattern, gradient и др.

## CLI / пакетная обработка (расширенный способ)

Для пакетной обработки можно вызвать Inkscape с actions или использовать прямой вызов класса (пример на Python):

```bash
python - <<'PY'
import inkex
from remove_no_color import RemoveNoColorObjects

svg_in = 'input.svg'
svg_out = 'output.svg'

doc = inkex.load_svg(svg_in)
ext = RemoveNoColorObjects()
class O:  # эмуляция опций
    remove_empty_groups = True
    opacity_zero_is_none = True
    display_none_is_invisible = False
ext.options = O()
ext.document = doc
ext.svg = doc.getroot()
ext.effect()

doc.write(svg_out)
print('Done ->', svg_out)
PY
```

## Ограничения
- Упрощённый парсинг CSS: поддерживаются только селекторы классов (`.class`).
- Не анализируются градиенты на фактическую прозрачность.
- Элементы с фильтрами / clip-path могут иметь визуализацию даже без обычной заливки.

## Идеи будущих улучшений
- Опция сохранения элементов с `filter`, `mask`, `clip-path`.
- Сбор статистики по удалённым тегам.
- Дополнительные тестовые SVG-примеры.

## Лицензия
(Добавьте информацию о лицензии, если нужно.)

---

## Расширение: Ungroup Text (Apply Transform)

Файл: `ungroup_apply_coords.py` + `ungroup_apply_coords.inx`

Назначение: Разгруппировать группы `<g>` с трансформацией, содержащие один `<text>`, "запекая" (`bake`) transform в координаты x/y самого `text` и его `tspan`.

### Установка
Поместите оба файла в ту же папку расширений (см. выше) и перезапустите Inkscape. Меню: Extensions → Очистка → Ungroup Text (Apply Transform).

### Параметры
| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| Только группы с одним <text> (`only_single_text`) | Обрабатывать только если в группе единственный значимый элемент — `<text>`. | true |
| Применять к tspan x/y (`apply_to_tspan`) | Применять матрицу и к координатам `tspan` (если заданы x/y). | true |

### Что делает
1. Для каждой группы `<g transform="...">` ищет единственный дочерний `<text>` (игнорируя `desc`/`title`).
2. Сливает матрицу группы и (если есть) матрицу самого текста.
3. Применяет итоговую матрицу к координатам `x`/`y` текста и его `tspan` (если включено).
4. Удаляет атрибуты `transform` у текста и группы.
5. Перемещает `<text>` на уровень выше и удаляет группу, если она опустела.

### Ограничения
- Не обрабатывает группы с несколькими графическими элементами (если включён only_single_text).
- Не изменяет `dx` / `dy` — только абсолютные `x` / `y`.
- Сложные матрицы (например с поворотом) приводят к смещению координат, но вращение/наклон будет потерян, если он был только в transform (для поворота корректное "запекание" в чистые x/y невозможно без пересчёта glyph layout). Поэтому расширение лучше подходит для чистых translate/scale.

### Совет
Если матрица включает rotate/skew — подумайте, нужно ли действительно разгруппировывать: текст изменит визуальное положение.

