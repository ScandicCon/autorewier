# Локальные шрифты

Сюда нужно положить 3 файла (скачать с fonts.google.com, формат woff2):

| Файл | Шрифт на Google Fonts |
|---|---|
| `Onest-Variable.woff2` | Onest (вес 400–800) |
| `Unbounded-Variable.woff2` | Unbounded (вес 600–800) |
| `PressStart2P-Regular.woff2` | Press Start 2P (400) |

Зачем: раньше шрифты грузились с `fonts.googleapis.com`, который в РФ недоступен
без VPN — страница ждала внешний ресурс. Теперь они отдаются с нашего домена.

Если файлов нет — сайт не сломается: в `styles.css` прописан системный фолбэк
(`system-ui`), просто шрифт будет обычным.
