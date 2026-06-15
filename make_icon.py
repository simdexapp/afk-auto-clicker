"""Generate icon.ico for the app (run once; re-run to tweak the look)."""
from engine import make_icon_image

img = make_icon_image(256)
img.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote icon.ico")
