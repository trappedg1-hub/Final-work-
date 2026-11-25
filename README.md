# Final-work-

Визуальная новелла-стрим: Тамагочи-гёрл у кресла, донаты, стримы и фан-сервис.

## Две версии арта

Игра живёт в двух стилях, переключаются кнопкой 🎨 в шапке (или параметром URL):

| стиль | адрес | арт | канон |
|---|---|---|---|
| аниме | `?style=anime` (по умолчанию) | `assets/art_day1_sgN.webp` | канон 1 — день 1 |
| реализм | `?style=real` | `assets/real/art_real_day1_sgN.webp` | канон 2 |

Выбор запоминается в `localStorage` (`fw_art_style`), так что ссылку с `?style=real`
достаточно открыть один раз.

### Что у каждого стиля своё

- **арт**: мастер 3:4 (аниме 3840×5120, реализм 2340×3120) + `_sm` 1170×1560;
- **эмоции**: `assets/art_emo_sgN_{blink,shy}.webp` и `assets/real/art_real_emo_sgN_{blink,shy}.webp`;
- **пропы груди**: `assets/chest_sgN_{l,r}.webp` и `assets/real/chest_real_sgN_{l,r}.webp`;
- **геометрия физики**: `BUST_GEO` (аниме) и `BUST_GEO_REAL` (реализм) в `index.html` —
  фигура в каноне 2 крупнее и сидит иначе, маски между стилями не переносятся.

Комната (`room_day1`, `room_fg`) общая: она фотореалистичная и стыкуется с передним
планом стола, поэтому второй раз её не рисуем.

## Канон 2 (реалистичный стиль)

Полный разбор рисоваки, замеры и правила генерации — `tools/canon2_style.md`.
Эталон — `images/raw_real/_canon2_hero.png`.

Сборка ассетов реалистичной версии:

```bash
python3 tools/match_style.py images/raw_real/_sg1.png --out images/raw_real/_g1.png  # доводка под эталон
python3 tools/prep_real.py        # ключ + ACNet + холст 3:4 + кадры эмоций
python3 tools/prep_real_chest.py  # пропы груди и окна под ними
node tools/build-static.mjs       # dist/ для Vercel
```

Порядок важен: `chest_patch` читает целый `_sm`, `punch_hole` идёт после него.
Повторный запуск `prep_real_chest.py` на уже пробитых кадрах удвоит прокол —
гонять только от чистых исходников.
