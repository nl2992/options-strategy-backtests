"""NeurIPS-2025-style matplotlib setup shared by every report notebook.

Presentation only: rcParams, one colour/marker per strategy, the out-of-sample shading helper, and a save helper.
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

# One soft, colour-blind-distinguishable colour per strategy, reused in every figure (markers differ as well,
# so figures survive greyscale).
STRAT_COL = dict(
    H1='#4E79A7', H2='#E08E45', H3='#5BA574', H4='#B07AA1', H5='#D9B23E', H6='#7FBFD8',
    S1='#2A6F97', S2='#BC4B51', S3='#7B6BA8', S4='#8A9A5B', S5='#E07A5F', S6='#6F9A96',
    S7='#A67C52', S8='#264653', S9='#E3A5A5', S10='#7A828A', F2='#222222')
STRAT_MARK = dict(H1='o', H2='s', H3='^', H4='D', H5='v', H6='P',
                  S1='o', S2='s', S3='^', S4='D', S5='v', S6='P', S7='X', S8='h', S9='<', S10='>', F2='*')
STRAT_HATCH = dict(H1='', H2='//', H3='\\\\', H4='..', H5='xx', H6='--',
                   S1='', S2='//', S3='\\\\', S4='..', S5='xx', S6='--', S7='++', S8='||', S9='oo', S10='**', F2='')

DEV_COL = '#4D5B6B'      # development-period neutral
OOS_COL = '#C8553D'      # out-of-sample (test / holdout) accent
TEST_BAND = '#EBEBEB'    # light grey band used for every out-of-sample period
GRID = '#C9C9C9'
INK = '#222222'


def setup():
    """Apply the NeurIPS-2025 'open look': white background, sans-serif, dashed light grid behind data."""
    mpl.rcParams.update({
        'figure.facecolor': 'white', 'axes.facecolor': 'white', 'savefig.facecolor': 'white',
        'figure.dpi': 110, 'font.family': 'sans-serif',
        'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
        'font.size': 9, 'axes.titlesize': 10, 'axes.titleweight': 'normal', 'axes.titlelocation': 'left',
        'axes.labelsize': 9, 'xtick.labelsize': 8.5, 'ytick.labelsize': 8.5, 'legend.fontsize': 8,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.edgecolor': INK, 'axes.linewidth': .8, 'axes.labelcolor': INK, 'text.color': INK,
        'xtick.color': INK, 'ytick.color': INK, 'xtick.direction': 'in', 'ytick.direction': 'in',
        'axes.grid': True, 'axes.axisbelow': True, 'grid.color': GRID, 'grid.linestyle': '--',
        'grid.linewidth': .5, 'grid.alpha': .8,
        'lines.linewidth': 1.6, 'lines.markersize': 4.5,
        'errorbar.capsize': 3, 'legend.frameon': False,
        'axes.prop_cycle': mpl.cycler(color=[STRAT_COL[k] for k in ('H1', 'H2', 'H3', 'H4', 'H5', 'H6')]),
        'savefig.bbox': 'tight', 'figure.constrained_layout.use': False,
    })


def shade_test(ax, start, end, label='test', zorder=0, label_y=.985, fontsize=7.5):
    """Light-grey band marking an out-of-sample period (same treatment everywhere). start/end may be dates or numbers."""
    if isinstance(start, (str, int)) and not isinstance(start, bool):
        try:
            start = pd.Timestamp(str(start)); end = pd.Timestamp(str(end))
        except Exception:
            pass
    ax.axvspan(start, end, color=TEST_BAND, zorder=zorder, lw=0)
    if label:
        ax.text(start + (end - start) / 2, label_y, label, transform=ax.get_xaxis_transform(), ha='center', va='top',
                fontsize=fontsize, color='#6b6b6b', style='italic', zorder=zorder + 1)


def style_err(containers):
    """Black, flat-capped error bars."""
    for c in containers:
        if hasattr(c, 'lines') and len(c.lines) > 2:
            for l in c.lines[1]:
                l.set_color('k')
            for l in c.lines[2]:
                l.set_color('k')


def save(fig, path, dpi=220):
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor='white')
    return path
