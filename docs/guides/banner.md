# Banner

`bf.Banner` puts Markdown text over a background image: a report cover, a section
opener or a social card. The text sits on a veil of the theme's background colour,
so it stays readable in every theme, dark ones included.

In practice you pass a file: `bf.Banner(text, image="cover.jpg")`. The examples
below draw their image with Matplotlib so they need no file. Any PNG, JPEG, GIF,
WebP or SVG works, as a path or as bytes.

## A fading veil

By default the veil fades in from the image side over 20 % of the width, and the
text column starts at `text_position` percent. `opacity` (0–100) sets how much the
veil covers the image under the text.

```{briefing-example}
:title: A banner with a fading veil

import io
import matplotlib.pyplot as plt
import numpy as np
import briefing as bf

# A stand-in for a photo: a smooth, colourful field.
x, y = np.meshgrid(np.linspace(0, 6, 300), np.linspace(0, 3, 150))
fig = plt.figure(figsize=(12, 3), dpi=100)
fig.add_axes((0, 0, 1, 1)).contourf(x, y, np.sin(x) * np.cos(y * 2) + x / 3, levels=24, cmap="viridis")
fig.axes[0].set_axis_off()
image = io.BytesIO()
fig.savefig(image, format="png", metadata={"Software": None})

report = bf.Banner(
    "# Q1 2024\n\n**Sales briefing** for the regional leads.",
    image=image.getvalue(),
    text_position=50,
    opacity=85,
    alt="Abstract contour pattern",
)
bf.save(report, "banner.html", name="Banner")
```

`side="left"` puts the text on the left, and the image clear on the right.
`focus=(x, y)`, in percent, picks the point of the image kept in view when the
banner crops it. At phone width, the image stacks above the text.

## A uniform veil

`fade=False` covers the whole image with one veil at `opacity`. It suits textures
and full-width backgrounds; the text still follows `text_position`.

```{briefing-example}
:title: A banner with a uniform veil

import io
import matplotlib.pyplot as plt
import numpy as np
import briefing as bf

rng = np.random.default_rng(5)
fig = plt.figure(figsize=(12, 2.5), dpi=100)
fig.add_axes((0, 0, 1, 1)).imshow(rng.random((25, 120)), cmap="magma", aspect="auto")
fig.axes[0].set_axis_off()
image = io.BytesIO()
fig.savefig(image, format="png", metadata={"Software": None})

report = bf.Banner(
    "## Appendix\n\nMethod, sources and caveats.",
    image=image.getvalue(),
    fade=False,
    opacity=70,
    text_position=8,
    height=200,
)
bf.save(report, "banner-uniform.html", name="Banner")
```

The image is embedded once, as a data URI, at its original size: briefing doesn't
resize it. Files over 2 MB trigger a warning, since they make the report heavy;
see {doc}`assets`.
