# shared PyInstaller config for MIYOYAZU DASH
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import os
DROP = ('avcodec', 'avformat', 'avutil', 'swresample', 'swscale', 'libp3ffmpeg', 'fmod', 'assimp', 'ptloader',
        'bullet', 'pandaode', 'pandaai', 'vrpn', 'p3vision', 'pandadx9', 'd3dx9', 'cgd3d9', 'pandaphysics', 'pandafx')
BINS = [x for x in collect_dynamic_libs('panda3d') if not any(k in os.path.basename(x[0]).lower() for k in DROP)]
DATAS = collect_data_files('panda3d', includes=['etc/*'])
ASSETS = [(f, 'assets') for f in ('assets/menu_bg.jpg', 'assets/poster.jpg', 'assets/icon.ico', 'assets/icon.png',
                                  'assets/ui_font.ttf', 'assets/ui_plain.ttf', 'assets/THIRD_PARTY.txt')]
ASSETS += [('assets/sfx', 'assets/sfx')]
HIDDEN = ['panda3d.core', 'panda3d.direct', 'direct.showbase.ShowBase', 'direct.gui.DirectGui', 'direct.filter.FilterManager',
          'md_gfx', 'md_world', 'md_play', 'fs_geom', 'numpy']
EXCL = ['matplotlib', 'scipy', 'pandas', 'IPython', 'pytest', 'tkinter', 'PIL', 'cv2', 'wx', 'PyQt5', 'imageio_ffmpeg', 'onnxruntime']
HIDDEN += ['truststore', 'certifi']
DATAS += collect_data_files('certifi')
