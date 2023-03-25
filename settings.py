# {
#     "title": "Jarvis Voice Assistant",
#     "background": "background.png",
#     "format": "UDBZ",
#     "compression-level": 9,
#     "window": { "position": { "x": 100, "y": 100 },
#                 "size": { "width": 640, "height": 300 } },
#     "contents": [
#         { "x": 140, "y": 165, "type": "file", "path": "dist/Jarvis.app" },
#         { "x": 480, "y": 165, "type": "link", "path": "/Applications" }
#     ],
#     "volume_size": "3g",
#     "size": "3g"
# }
import os.path
import plistlib

#
# Example settings file for dmgbuild
#

# Use like this: dmgbuild -s settings.py "Test Volume" test.dmg

# You can actually use this file for your own application (not just TextEdit)
# by doing e.g.
#
#   dmgbuild -s settings.py -D app=/path/to/My.app "My Application" MyApp.dmg

# .. Useful stuff ..............................................................

application = defines.get("app", "/System/Applications/TextEdit.app")  # noqa: F821
appname = os.path.basename(application)


def icon_from_app(app_path):
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
    icon_name = plist["CFBundleIconFile"]
    icon_root, icon_ext = os.path.splitext(icon_name)
    if not icon_ext:
        icon_ext = ".icns"
    icon_name = icon_root + icon_ext
    return os.path.join(app_path, "Contents", "Resources", icon_name)


# .. Basics ....................................................................

# Uncomment to override the output filename
# filename = 'test.dmg'

# Uncomment to override the output volume name
# volume_name = 'Test'

# Volume format (see hdiutil create -help)
format = defines.get("format", "UDBZ")  # noqa: F821

# Compression level (if relevant)
# compression_level = 9

# Volume size
size = defines.get("size", "3g")  # noqa: F821

# Files to include
files = [application]

# Symlinks to create
symlinks = {"Applications": "/Applications"}

# Files to hide
# hide = [ 'Secret.data' ]

# Files to hide the extension of
# hide_extension = [ 'README.rst' ]

# Volume icon
#
# You can either define icon, in which case that icon file will be copied to the
# image, *or* you can define badge_icon, in which case the icon file you specify
# will be used to badge the system's Removable Disk icon. Badge icons require
# pyobjc-framework-Quartz.
#
# icon = '/path/to/icon.icns'
badge_icon = icon_from_app(application)

# Where to put the icons
icon_locations = {appname: (140, 120), "Applications": (500, 120)}

# .. Window configuration ......................................................

# Background
#
# This is a STRING containing any of the following:
#
#    #3344ff          - web-style RGB color
#    #34f             - web-style RGB color, short form (#34f == #3344ff)
#    rgb(1,0,0)       - RGB color, each value is between 0 and 1
#    hsl(120,1,.5)    - HSL (hue saturation lightness) color
#    hwb(300,0,0)     - HWB (hue whiteness blackness) color
#    cmyk(0,1,0,0)    - CMYK color
#    goldenrod        - X11/SVG named color
#    builtin-arrow    - A simple built-in background with a blue arrow
#    /foo/bar/baz.png - The path to an image file
#
# The hue component in hsl() and hwb() may include a unit; it defaults to
# degrees ('deg'), but also supports radians ('rad') and gradians ('grad'
# or 'gon').

# Other color components may be expressed either in the range 0 to 1, or
# as percentages (e.g. 60% is equivalent to 0.6).
background = "background.png"

show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
sidebar_width = 180

# Window position in ((x, y), (w, h)) format
window_rect = ((100, 100), (640, 280))

# Select the default view; must be one of
#
#    'icon-view'
#    'list-view'
#    'column-view'
#    'coverflow'
#
default_view = "icon-view"

# General view configuration
show_icon_preview = False

# Set these to True to force inclusion of icon/list view settings (otherwise
# we only include settings for the default view)
include_icon_view_settings = "auto"
include_list_view_settings = "auto"

# .. Icon view configuration ...................................................

arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
scroll_position = (0, 0)
label_pos = "bottom"  # or 'right'
text_size = 16
icon_size = 128

# .. List view configuration ...................................................

# Column names are as follows:
#
#   name
#   date-modified
#   date-created
#   date-added
#   date-last-opened
#   size
#   kind
#   label
#   version
#   comments
#
list_icon_size = 16
list_text_size = 12
list_scroll_position = (0, 0)
list_sort_by = "name"
list_use_relative_dates = True
list_calculate_all_sizes = (False,)
list_columns = ("name", "date-modified", "size", "kind", "date-added")
list_column_widths = {
    "name": 300,
    "date-modified": 181,
    "date-created": 181,
    "date-added": 181,
    "date-last-opened": 181,
    "size": 97,
    "kind": 115,
    "label": 100,
    "version": 75,
    "comments": 300,
}
list_column_sort_directions = {
    "name": "ascending",
    "date-modified": "descending",
    "date-created": "descending",
    "date-added": "descending",
    "date-last-opened": "descending",
    "size": "descending",
    "kind": "ascending",
    "label": "ascending",
    "version": "ascending",
    "comments": "ascending",
}

# .. License configuration .....................................................

# Text in the license configuration is stored in the resources, which means
# it gets stored in a legacy Mac encoding according to the language.  dmgbuild
# will *try* to convert Unicode strings to the appropriate encoding, *but*
# you should be aware that Python doesn't support all of the necessary encodings;
# in many cases you will need to encode the text yourself and use byte strings
# instead here.

# Recognized language names are:
#
#  af_ZA, ar, be_BY, bg_BG, bn, bo, br, ca_ES, cs_CZ, cy, da_DK, de_AT, de_CH,
#  de_DE, dz_BT, el_CY, el_GR, en_AU, en_CA, en_GB, en_IE, en_SG, en_US, eo,
#  es_419, es_ES, et_EE, fa_IR, fi_FI, fo_FO, fr_001, fr_BE, fr_CA, fr_CH,
#  fr_FR, ga-Latg_IE, ga_IE, gd, grc, gu_IN, gv, he_IL, hi_IN, hr_HR, hu_HU,
#  hy_AM, is_IS, it_CH, it_IT, iu_CA, ja_JP, ka_GE, kl, ko_KR, lt_LT, lv_LV,
#  mk_MK, mr_IN, mt_MT, nb_NO, ne_NP, nl_BE, nl_NL, nn_NO, pa, pl_PL, pt_BR,
#  pt_PT, ro_RO, ru_RU, se, sk_SK, sl_SI, sr_RS, sv_SE, th_TH, to_TO, tr_TR,
#  uk_UA, ur_IN, ur_PK, uz_UZ, vi_VN, zh_CN, zh_TW

license = {
    "default-language": "en_US",
    "licenses": {
        # For each language, the text of the license.  This can be plain text,
        # RTF (in which case it must start "{\rtf1"), or a path to a file
        # containing the license text.  If you're using RTF,
        # watch out for Python escaping (or read it from a file).
        "en_US": b"""{\\rtf1\\ansi\\ansicpg1252\\cocoartf2708
\\cocoatextscaling0\\cocoaplatform0{\\fonttbl\\f0\\fnil\\fcharset0 HelveticaNeue-Bold;\\f1\\fnil\\fcharset0 HelveticaNeue;}
{\\colortbl;\\red255\\green255\\blue255;\\red0\\green0\\blue0;}
{\\*\\expandedcolortbl;;\\cssrgb\\c0\\c0\\c0\\cname textColor;}
\\margl1440\\margr1440\\vieww17400\\viewh12040\\viewkind0
\\deftab720
\\pard\\pardeftab720\\sa400\\partightenfactor0
\\f0\\b\\fs36 \\cf2 \\cb3 \\expnd0\\expndtw0\\kerning0
\\outl0\\strokewidth0 \\strokec4 SOFTWARE TESTING LICENSE AGREEMENT\\
\\f1\\b0\\fs32 This Software Testing License Agreement (the "Agreement") is entered into as of the date of installation (the "Effective Date") by and between Elias Weston-Farber ("Licensor") and the individual or entity installing the software ("Licensee").\\
WHEREAS, Licensor owns the proprietary software known as Jarvis (the "Software");\\
WHEREAS, Licensee desires to use the Software for testing purposes only;\\
NOW, THEREFORE, in consideration of the mutual covenants and promises contained herein, the parties agree as follows:\\
\\pard\\tx720\\pardeftab720\\partightenfactor0
\\b \\cf2 \\strokec4 1. License Grant.\\
\\b0 Subject to the terms and conditions of this Agreement, Licensor hereby grants Licensee a non-exclusive, non-transferable, non-sublicensable, and revocable license to use the Software for testing purposes only.\\
\\
\\b 2. Restrictions on Use.\\
\\b0 Licensee shall not: (a) redistribute, sublicense, sell, lease, lend, or otherwise transfer the Software; (b) use the Software for any commercial purposes; (c) use the Software for any purpose that violates applicable law; or (d) reverse engineer, decompile, disassemble, or otherwise attempt to derive the source code of the Software.\\
\\
\\b 3. Intellectual Property Rights.\\
\\b0 Licensor retains all rights, title, and interest in and to the Software, including all intellectual property rights therein. Nothing in this Agreement shall be construed to transfer ownership of the Software or any intellectual property rights associated therewith to Licensee.\\
\\
\\b 4. Termination.\\
\\b0 This Agreement shall terminate automatically upon the completion of Licensee's testing of the Software or upon any breach of this Agreement by Licensee. Upon termination, Licensee\\
}""",
    },
    "buttons": {
        # For each language, text for the buttons on the licensing window.
        #
        # Default buttons and text are built-in for the following languages:
        #
        #   da_DK: Danish
        #   de_DE: German
        #   en_AU: English (Australian)
        #   en_GB: English (UK)
        #   en_NZ: English (New Zealand)
        #   en_US: English (US)
        #   es_ES: Spanish
        #   fr_CA: French (Canadian)
        #   fr_FR: French
        #   it_IT: Italian
        #   ja_JP: Japanese
        #   nb_NO: Norsk
        #   nl_BE: Flemish
        #   nl_NL: Dutch
        #   pt_BR: Brazilian Portuguese
        #   pt_PT: Portugese
        #   sv_SE: Swedish
        #   zh_CN: Simplified Chinese
        #   zh_TW: Traditional Chinese
        #
        # You don't need to specify them for those languages; if you fail to
        # specify them for some other language, English will be used instead.
        "en_US": (
            b"English",
            b"Agree!",
            b"Disagree!",
            b"Print!",
            b"Save!",
            b'Do you agree or not? Press "Agree" or "Disagree".',
        ),
    },
}