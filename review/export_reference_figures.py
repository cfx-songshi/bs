"""Export the experiment figures the foundation slides cite, from the reference PDFs.

    python review\\export_reference_figures.py [folder holding the papers]

Writes review/ref_figures/*.png. The papers themselves are not in the repository (they are
published articles), so the folder has to be supplied; the default is where the copies used
to build this deck live. The PNGs are gitignored, and the deck embeds them, which keeps the
slides reproducible on this machine without redistributing the articles.

Why crop the rendered page instead of pulling embedded images out: these journals draw most
figures as vector art, and there would be no embedded image to pull. The crop region comes
from the figure's own caption — a figure sits between the text block above it and that caption
— so nothing here is a hand-measured box.
"""
import argparse
import glob
import os

import pymupdf
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, 'ref_figures')
DEFAULT_SRC = r'C:\Users\29795\Downloads\毕设知识库\已有工作基础'
ZOOM = 2.6

# (a substring of that paper's file name, page, the caption's opening words, output name,
# description). The paper is found by name, not by its index in a sorted listing: an index
# silently points at a different paper as soon as the folder or the file names change, which
# is what happened the first time this ran against the library folder — it cropped a figure
# from the gas turbine paper and called it the gearbox signal. The caption prefix is long
# enough to be unique within its paper for the same reason.
#
# Chosen for what the simulations need: the specimen, the measurement chain, what damage looks
# like, and how the signal responds to it.
WANTED = [
    ('Zhao_2025', 10, 'Figure 8. Composite structures', 'imp_specimen',
     '碳纤维加强板试件（实拍 + 尺寸图）'),
    ('Zhao_2025', 10, 'Figure 9. Data acquisition system', 'imp_chain',
     'PZT 采集系统与冲击力锤'),
    ('FAA-ELM', 5, 'Fig. 3. Gear transmission test system', 'gear_rig', '齿轮传动试验台'),
    ('FAA-ELM', 5, 'Fig. 4. SMART Layer', 'gear_smart', 'SMART layer 与 PZT 布置'),
    ('FAA-ELM', 6, 'Fig. 5. Typical Gear faults', 'gear_faults', '齿根裂纹与齿面磨损'),
    ('FAA-ELM', 7, 'Fig. 9. Scattered signals', 'gear_signals', '三种健康状态的散射信号'),
    ('In_Situ_Monitoring', 5, 'Fig. 8. Experimental tensile testing', 'bolt_rig',
     '螺栓接头拉伸试验系统'),
    ('In_Situ_Monitoring', 7, 'Fig. 16. Layout schemes', 'bolt_layouts',
     '三种失效模式的传感器布局'),
    ('In_Situ_Monitoring', 8, 'Fig. 17. Load', 'bolt_curve', '净拉伸的载荷-位移与电阻曲线'),
    ('In_Situ_Monitoring', 9, 'Fig. 20. Damage around holes', 'bolt_damage',
     '三种失效模式的孔周损伤'),
    ('Embedded_Piezoresistive', 6, 'Fig. 11. Photographs of sensor layouts', 'emb_photos',
     '三种失效模式的传感器实拍'),
    ('Embedded_Piezoresistive', 9, 'Fig. 20. Cross section', 'emb_section', '嵌入传感层的截面'),
    ('Embedded_Piezoresistive', 10, 'Fig. 22. Load', 'emb_curve', '净拉伸的载荷-电阻曲线'),
]

# A figure that carries two panels stacked vertically is unusable as one image on a slide: the
# specimen figure is 1:2, so on a slide it would either be tiny or taller than the page.
# Splitting it gives the panel that belongs next to "试件" and the panel that belongs next to
# "布局". The gap between the fractions is the "(a)" panel label printed between them, which
# belongs to neither half. Fractions were read off the rendered crop, which is why the build
# prints both parts.
SPLITS = {'imp_specimen': {'a': (0.0, 0.465), 'b': (0.487, 1.0)}}


def openable(path):
    """Windows refuses paths longer than 260 characters unless told not to."""
    return path if os.path.exists(path) else '\\\\?\\' + os.path.abspath(path)


def crop(document, page_number, label, pad=6):
    page = document[page_number - 1]
    blocks = page.get_text('blocks')
    caption = next((b for b in blocks if ' '.join(b[4].split()).startswith(label)), None)
    if caption is None:
        return None
    x0, y0, x1, y1 = caption[:4]
    top = page.rect.y0 + 8
    for block in blocks:
        bx0, by0, bx1, by1 = block[:4]
        if by1 <= y0 - 1 and bx1 > x0 and bx0 < x1:
            top = max(top, by1)
    region = pymupdf.Rect(x0 - pad, top + 3, x1 + pad, y0 - 2)
    if region.height < 40 or region.width < 40:
        return None
    pixmap = page.get_pixmap(clip=region, matrix=pymupdf.Matrix(ZOOM, ZOOM))
    return Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples)


def save(image, name, title):
    target = os.path.join(DST, '%s.png' % name)
    image.save(target, optimize=True)
    print('  %-16s %4d x %4d px  %.2f MB  %s'
          % (name, image.width, image.height, os.path.getsize(target) / 1e6, title))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', nargs='?', default=DEFAULT_SRC,
                        help='folder holding the reference PDFs')
    options = parser.parse_args()
    os.makedirs(DST, exist_ok=True)

    paths = sorted(glob.glob(os.path.join(options.source, '*.pdf')))
    if not paths:
        raise SystemExit('no PDFs in %s' % options.source)
    documents, crops = {}, []
    for keyword, page, label, name, title in WANTED:
        if keyword not in documents:
            matches = [p for p in paths if keyword in os.path.basename(p)]
            if len(matches) != 1:
                raise SystemExit('%d files match "%s" in %s; expected exactly one'
                                 % (len(matches), keyword, options.source))
            documents[keyword] = pymupdf.open(openable(matches[0]))
        image = crop(documents[keyword], page, label)
        if image is None:
            print('  MISSED %s (%s page %d %s)' % (name, keyword, page, label))
            continue
        if name in SPLITS:
            parts = SPLITS[name]
            pieces = []
            for suffix in ('a', 'b'):
                share, label = parts[suffix], suffix
                top = int(image.height * share[0])
                bottom = int(image.height * share[1])
                piece = image.crop((0, top, image.width, bottom))
                save(piece, name + '_' + label, title + '（%s 部分）' % label)
                pieces.append((name + '_' + label, title + '（%s）' % label, piece))
            crops.extend(pieces)
        else:
            save(image, name, title)
            crops.append((name, title, image))
    for document in documents.values():
        document.close()

    # One contact sheet, so every crop can be judged in a single look.
    cell, label_height, columns = 430, 26, 4
    rows = (len(crops) + columns - 1) // columns
    sheet = Image.new('RGB', (cell * columns, (cell + label_height) * rows), 'white')
    draw = ImageDraw.Draw(sheet)
    for position, (name, title, image) in enumerate(crops):
        column, row = position % columns, position // columns
        left, top = column * cell, row * (cell + label_height)
        thumb = image.copy()
        thumb.thumbnail((cell - 8, cell - 8), Image.LANCZOS)
        sheet.paste(thumb, (left + 4, top + label_height + 4))
        draw.text((left + 6, top + 7), '%d %s' % (position + 1, name), fill='black')
    sheet.save(os.path.join(DST, '_contact.png'))
    print('  %d figures -> %s' % (len(crops), DST))


if __name__ == '__main__':
    main()
