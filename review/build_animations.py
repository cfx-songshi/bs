"""Turn the exported Abaqus frame sequences into GIFs, and compose the still views.

    python review\\build_animations.py

The frames come from export_abaqus_views.py, which writes one PNG per frame with the
contour legend pinned, so the animation shows the wave moving rather than the colour scale
rescaling. Two things are worth knowing about how the GIFs are built:

* One palette for the whole animation. Quantising each frame on its own gives every frame
  its own palette, and the whole image shimmers as a result.
* The frames are downscaled before quantising. An Abaqus viewport capture is 1000 px wide
  and 24 of them at 256 colours is several megabytes of base64 inside the report.

Anything not present is skipped with a message rather than failing, because the impact
frames and the wave frames are exported by separate CAE runs.
"""
import glob
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWS = os.path.join(HERE, 'abaqus_views')
FIGURES = os.path.join(HERE, 'figures')

GIF_WIDTH = 760
GIF_COLOURS = 128
# Frame duration at normal speed, and the factor the deck plays at. A frame every 130 ms is
# a 7.7 frames per second flip book, which is fast for a wave that crosses the plate in
# about forty microseconds. A GIF stores its frame delay in hundredths of a second, so 0.7x
# (185.7 ms) is not representable; 190 ms is the nearest step and gives 0.684x, which is
# closer than the 180 ms step's 0.722x.
BASE_MS = 130
PLAYBACK_SPEED = 0.7
GIF_MS = 190


def opaque(path):
    """Open an Abaqus viewport capture as opaque RGB.

    CAE writes a palette PNG carrying a transparency entry, and converting it to RGB turns
    that entry into the colour tuple (254, 254, 254). Left in place it puts the near white
    background into the image's info as a transparency *colour*, which the GIF writer then
    tries to use as a palette index and crashes on. Dropping the key makes the background
    the plain white it looks like.
    """
    image = Image.open(path).convert('RGB')
    image.info.pop('transparency', None)
    return image


def autocrop(image, margin=0.06):
    """Trim the viewport background off a model view.

    Abaqus draws the mesh in solid green against a dark gradient, so the model is where the
    green is. A capture of a 100 x 100 x 2 mm plate is mostly empty background, which is why
    the pair of model views montaged side by side came out a 6.7 : 1 strip and shrank to a
    sliver on a slide. Rows and columns count as model only when they carry a few per cent of
    the green, which is what keeps the little coordinate triad in the corner out of the box.
    """
    array = np.asarray(image.convert('RGB')).astype(int)
    red, green, blue = array[:, :, 0], array[:, :, 1], array[:, :, 2]
    mask = (green > 90) & (green > red * 1.4) & (green > blue * 1.4)
    height, width = mask.shape
    rows = np.where(mask.sum(axis=1) > 0.02 * width)[0]
    columns = np.where(mask.sum(axis=0) > 0.02 * height)[0]
    if not len(rows) or not len(columns):
        return image
    pad_y = int((rows[-1] - rows[0]) * margin) + 8
    pad_x = int((columns[-1] - columns[0]) * margin) + 8
    return image.crop((max(0, columns[0] - pad_x), max(0, rows[0] - pad_y),
                       min(width, columns[-1] + pad_x), min(height, rows[-1] + pad_y)))


def frames_for(pattern):
    return sorted(glob.glob(os.path.join(VIEWS, pattern)))


def to_gif(paths, target):
    """One shared palette, downscaled first, looping forever."""
    images = []
    for path in paths:
        image = opaque(path)
        height = int(round(image.height * GIF_WIDTH / float(image.width)))
        images.append(image.resize((GIF_WIDTH, height), Image.LANCZOS))
    palette = images[0].quantize(colors=GIF_COLOURS, method=Image.MEDIANCUT)
    quantised = [palette] + [image.quantize(palette=palette, dither=Image.NONE)
                             for image in images[1:]]
    quantised[0].save(target, save_all=True, append_images=quantised[1:],
                      duration=GIF_MS, loop=0, optimize=False)
    # Read the delay back rather than reporting what was asked for: the format stores it in
    # hundredths of a second, so the requested figure is not what ends up in the file.
    with Image.open(target) as saved:
        stored = saved.info.get('duration', GIF_MS)
    print('  %s (%.2f MB, %d frames, %d x %d, %d ms/frame = %.3gx speed)'
          % (os.path.basename(target), os.path.getsize(target) / 1e6, len(quantised),
             images[0].width, images[0].height, stored, BASE_MS / float(stored)))
    return target


def layers_view(source, target, keep=0.30):
    """Close up of the plate's cut edge, where the eight plies read as eight rows.

    The band the plate and ball occupy is found by autocrop rather than by a hand written box:
    a front view of a 2 mm plate fills a couple of dozen pixels of a 1200 pixel tall frame, so
    a fixed crop read off one export breaks as soon as the capture size changes. Cropping the
    central 30 per cent of the width afterwards leaves each ply about ten pixels tall, which
    at double size is enough to count them.
    """
    band = autocrop(opaque(source), margin=0.35)
    width, height = band.size
    left = int(width * (0.5 - keep / 2.0))
    crop = band.crop((left, 0, left + int(width * keep), height))
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    crop.save(target, optimize=True)
    print('  %s (%.2f MB, %d x %d)'
          % (os.path.basename(target), os.path.getsize(target) / 1e6,
             crop.width, crop.height))
    return target


def montage(paths, target, columns=2, gap=14, width=1400, crop=False,
            background=(255, 255, 255)):
    """A side by side grid, for the still views and for a printable key frame strip."""
    columns = min(columns, len(paths))
    images = []
    for path in paths:
        image = opaque(path)
        if crop:
            image = autocrop(image)
        scale = width / float(columns * image.width)
        images.append(image.resize((int(image.width * scale), int(image.height * scale)),
                                   Image.LANCZOS))
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * cell_w + (columns - 1) * gap,
                              rows * cell_h + (rows - 1) * gap), background)
    for index, image in enumerate(images):
        column, row = index % columns, index // columns
        canvas.paste(image, (column * (cell_w + gap), row * (cell_h + gap)))
    canvas.save(target, optimize=True)
    print('  %s (%.2f MB, %d panels)'
          % (os.path.basename(target), os.path.getsize(target) / 1e6, len(images)))
    return target


def main():
    if not os.path.isdir(FIGURES):
        os.makedirs(FIGURES)
    print('animations')
    wave_frames = frames_for('wav_base_wave_*.png')
    if wave_frames:
        to_gif(wave_frames, os.path.join(FIGURES, 's7_wave_animation.gif'))
        # Four evenly spaced frames as well, for reading on paper and for anyone who cannot
        # play the animation.
        picks = [wave_frames[index] for index in (2, 7, 12, 18)]
        montage(picks, os.path.join(FIGURES, 's7_wave_frames.png'), columns=2, width=1200)
    else:
        print('  no wave frames yet')

    impact_frames = frames_for('imp_mid_impact_*.png')
    if impact_frames:
        to_gif(impact_frames, os.path.join(FIGURES, 's6_impact_animation.gif'))
    else:
        print('  no impact frames yet')

    print('stills')
    # The isometric view on its own rather than beside the front view: with the background
    # cropped away the front view becomes a very wide sliver, and the layering it was there to
    # show is the next figure's job.
    iso = frames_for('imp_mid_model.png')
    front = frames_for('imp_mid_model_front.png')
    if iso:
        montage(iso, os.path.join(FIGURES, 's6_abaqus_model.png'), columns=1,
                width=1100, crop=True)
        if front:
            layers_view(front[0], os.path.join(FIGURES, 's6_layers.png'))
    else:
        print('  no impact model views yet')
    wave_views = frames_for('wav_base_model.png')
    if wave_views:
        montage(wave_views, os.path.join(FIGURES, 's7_abaqus_model.png'), columns=1,
                width=1100, crop=True)
    else:
        print('  no wave model views yet')


if __name__ == '__main__':
    main()
