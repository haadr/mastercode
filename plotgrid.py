#!/usr/bin/python3
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np


# Show a grid plot of values using matplotlib
def plotgrid(data, title="plotgrid", show=True, dpi=1200, saveFigure=False, labels=None, normalized=False, alpha=0.8):

    # Calculate ticks
    xticks_major = np.arange(0.5,len(data[0]), 1)
    yticks_major = np.arange(0.5,len(data), 1)

    xticks_minor = np.arange(0,len(data[0]), 1)
    yticks_minor = np.arange(0,len(data), 1)

    fig,ax = plt.subplots()

    if normalized:
        ax.imshow(data, vmin=0, vmax=1,cmap=plt.get_cmap('hot'),interpolation='nearest', alpha=alpha)
    else:
        ax.imshow(data, cmap=plt.get_cmap('hot'),interpolation='nearest', alpha=alpha)

    for i,row in enumerate(data):
        for j,col in enumerate(row):
            # Add percentage sign
            if j == len(row)-1:
                ax.text(j, i, '%.0f' % col + '%', va='center', ha='center', fontsize=17)
            else:
                ax.text(j, i, '%.0f' % col, va='center', ha='center', fontsize=17)

    ax.set_xticks(xticks_major)
    ax.set_yticks(yticks_major)
    ax.set_xticks(xticks_minor, minor=True)
    ax.set_yticks(yticks_minor, minor=True)

    ax.xaxis.tick_top()

    if(labels is not None):
        # ax.set_xticklabels(labels[0], minor=True, fontsize=17, rotation=45, ha="left")
        ax.set_xticklabels(labels[0], minor=True, fontsize=17, rotation=0, ha="center")
        ax.set_yticklabels(labels[1], minor=True, fontsize=17)
    else:
        ax.set_xticklabels(xticks_minor, minor=True)
        ax.set_yticklabels(yticks_minor, minor=True)

    ax.set_yticklabels([])
    ax.set_xticklabels([])

    ax.grid()

    x,y = np.array([ [-0.5, -1.5], [-0.5, -1.5] ])
    ax.text( (len(data[0])-1)/2, -1, "Predicted class", va='center', ha='center', rotation=0, fontsize=13)
    ax.text( -1, (len(data)-1)/2, "Actual class", va='center', ha='center', rotation=90, fontsize=13)

    if saveFigure:
        dtime = datetime.now().replace(microsecond=0)
        print("Saving confusion matrix to file...")
        outfile = title + "_" + str(dtime.isoformat()) + ".pdf"
        plt.savefig(outfile, dpi=dpi, bbox_inches='tight')
        print("Saved confusion matrix to {}".format(outfile))

    if show:
        plt.tight_layout()
        # "fig.subplots_adjust(bottom=0.1)
        plt.show()
