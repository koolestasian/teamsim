"""Render six illustrated research examples. Optional docs dependency: matplotlib.

All conversations and interfaces are fictional illustrations, not executed tests.
The paper counts are checked against the bibliography. Run this file to regenerate.
"""
import csv
import re
from collections import Counter
from html import escape
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon
from matplotlib.text import Text

ROOT = Path(__file__).resolve().parent
INK, PAPER, WHITE = "#142d32", "#f3f4ed", "#ffffff"
TEAL, LIME, CORAL, GRAY = "#147565", "#dcf28b", "#e97759", "#657a7b"
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK,
                     "svg.fonttype": "none", "svg.hashsalt": "teamsim-scenes"})


def scene():
    fig = plt.figure(figsize=(12, 9), facecolor=PAPER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set(xlim=(0, 1200), ylim=(900, 0))
    ax.axis("off")
    return fig, ax


def text(ax, x, y, words, size=32, color=INK, bold=False, align="left"):
    return ax.text(x, y, words, fontsize=size, color=color, weight="bold" if bold else "normal",
                   ha=align, va="center", linespacing=1.2)


def card(ax, x, y, w, h, fill=WHITE, radius=24, edge="none", lw=2):
    patch = FancyBboxPatch((x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}", facecolor=fill,
        edgecolor=edge, linewidth=lw)
    ax.add_patch(patch)
    return patch


def arrow(ax, start, end, color=INK, curve=0):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=30,
        linewidth=4, color=color, connectionstyle=f"arc3,rad={curve}"))


def check(ax, x, y, scale=1, color=TEAL):
    ax.plot([x-20*scale, x-4*scale, x+26*scale],
            [y, y+18*scale, y-24*scale], color=color, linewidth=6*scale,
            solid_capstyle="round", solid_joinstyle="round")


def cross(ax, x, y, scale=1, color=CORAL):
    for sign in (-1, 1):
        ax.plot([x-20*scale, x+20*scale], [y-sign*20*scale, y+sign*20*scale],
                color=color, linewidth=6*scale, solid_capstyle="round")


def person(ax, x, y, fill=TEAL, scale=1):
    ax.add_patch(Circle((x, y-35*scale), 28*scale, facecolor=fill, edgecolor=INK, linewidth=2))
    ax.add_patch(FancyBboxPatch((x-45*scale, y+2*scale), 90*scale, 65*scale,
        boxstyle=f"round,pad=0,rounding_size={30*scale}", facecolor=fill, edgecolor=INK, linewidth=2))


def bubble(ax, x, y, w, h, words, fill=WHITE, size=32):
    card(ax, x, y, w, h, fill)
    ax.add_patch(Polygon([[x+25,y+h-2],[x+25,y+h+24],[x+65,y+h-2]],
                         facecolor=fill, edgecolor="none"))
    text(ax, x+w/2, y+h/2, words, size=size, align="center", bold=True)


def calendar(ax, x, y, day, fill=LIME, w=240, h=250):
    card(ax, x, y, w, h, WHITE, edge=INK, lw=3)
    card(ax, x, y, w, 60, fill, radius=20)
    for dx in (55, w-55):
        ax.plot([x+dx,x+dx], [y-15,y+20], color=INK, linewidth=9, solid_capstyle="round")
    text(ax, x+w/2, y+145, day, size=47, bold=True, align="center")


def window(ax, x, y, w, h, title):
    card(ax, x+8, y+12, w, h, "#e1e5da")
    card(ax, x, y, w, h)
    for i in range(3):
        ax.add_patch(Circle((x+30+i*23,y+31),7,facecolor=CORAL if i==0 else "#d7dfd7"))
    text(ax, x+w-30, y+35, title, size=26, color=GRAY, align="right")
    ax.plot([x+20,x+w-20],[y+67,y+67],color="#e8ebe4",linewidth=2)


def robot(ax, x, y):
    card(ax,x-63,y-45,126,95,TEAL,edge=INK,lw=3)
    for dx in (-25,25):
        ax.add_patch(Circle((x+dx,y-4),8,facecolor=LIME))
    ax.plot([x,x],[y-45,y-70],color=INK,linewidth=3)
    ax.add_patch(Circle((x,y-75),7,facecolor=CORAL))
    ax.plot([x-20,x+20],[y+25,y+25],color=LIME,linewidth=4)


def save(fig, name, description):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in fig.findobj(Text):
        if not label.get_visible() or not label.get_text().strip():
            continue
        b=label.get_window_extent(renderer)
        assert b.x0 >= 0 and b.y0 >= 0 and b.x1 <= fig.bbox.width and b.y1 <= fig.bbox.height, (name,label.get_text())
    fig.savefig(ROOT/f"{name}.png",dpi=160,facecolor=PAPER)
    path=ROOT/f"{name}.svg"
    fig.savefig(path,facecolor=PAPER,metadata={"Date":None})
    svg=path.read_text(encoding="utf-8")
    root=re.search(r"<svg\b[^>]*>",svg)
    opening=root.group()[:-1]+' role="img" aria-labelledby="title">'
    svg=svg[:root.start()]+opening+'<title id="title">'+escape(description)+'</title>'+svg[root.end():]
    path.write_text("\n".join(line.rstrip() for line in svg.splitlines())+"\n",encoding="utf-8",newline="\n")
    plt.close(fig)


def testing():
    fig,ax=scene()
    window(ax,70,65,1060,335,"# launch")
    person(ax,160,245,TEAL,.85)
    bubble(ax,255,190,785,115,"Launch moved to Friday.",LIME,35)
    arrow(ax,(360,430),(290,535),TEAL)
    window(ax,70,555,650,265,"your product")
    robot(ax,170,710)
    text(ax,285,675,"Launch day?",size=32)
    text(ax,285,750,"Friday.",size=43,bold=True)
    calendar(ax,825,550,"FRI",w=280,h=270)
    check(ax,1060,785,1.05)
    arrow(ax,(735,700),(810,700))
    save(fig,"plant-and-check","A fictional teammate says launch moved to Friday. The product answers Friday, matching the calendar.")


def update():
    fig,ax=scene()
    calendar(ax,90,100,"THU",fill="#e8e9e2",w=360,h=330)
    ax.plot([130,410],[355,240],color=CORAL,linewidth=9,solid_capstyle="round")
    arrow(ax,(495,275),(705,275))
    calendar(ax,750,100,"FRI",w=360,h=330)
    text(ax,270,495,"BEFORE",size=27,color=GRAY,align="center")
    text(ax,930,495,"NOW",size=27,color=TEAL,bold=True,align="center")
    robot(ax,200,690)
    bubble(ax,340,605,715,175,"Friday.",WHITE,48)
    check(ax,1045,800,1)
    save(fig,"changed-date","Thursday is crossed out and replaced by Friday. The product must answer with the current date.")


def minority():
    fig,ax=scene()
    for x,day,color in [(210,"THU",TEAL),(600,"THU",TEAL),(990,"FRI ONLY",CORAL)]:
        bubble(ax,x-160,80,320,125,day,LIME if x==990 else WHITE,32)
        person(ax,x,310,color,1.45)
    ax.plot([990,990],[420,510],color=CORAL,linewidth=4)
    ax.plot([210,210,600,600],[420,470,470,515],color="#c5cec5",linewidth=3)
    arrow(ax,(990,510),(855,615),CORAL)
    robot(ax,330,710)
    bubble(ax,475,610,620,180,"Friday.",WHITE,52)
    check(ax,1010,745,1.1)
    save(fig,"one-key-fact","Two teammates prefer Thursday. A third knows only Friday is approved. The product uses that decisive fact and answers Friday.")


def privacy():
    fig,ax=scene()
    # A sealed envelope travels toward the group, but a closed gate blocks it.
    card(ax,85,190,400,300,WHITE,edge=INK,lw=4)
    ax.plot([90,285,480],[205,350,205],color=TEAL,linewidth=5)
    ax.plot([100,205],[480,365],color="#b6c5b9",linewidth=3)
    ax.plot([475,370],[480,365],color="#b6c5b9",linewidth=3)
    card(ax,230,325,110,100,TEAL,radius=15)
    ax.add_patch(plt.matplotlib.patches.Arc((285,325),70,100,theta1=180,theta2=360,color=TEAL,linewidth=10))
    ax.add_patch(Circle((285,365),9,facecolor=LIME))
    text(ax,285,565,"PRIVATE",size=36,bold=True,align="center")
    arrow(ax,(520,350),(705,350),GRAY)
    ax.plot([665,665],[225,480],color=CORAL,linewidth=15,solid_capstyle="round")
    cross(ax,665,170,1.25)
    for x,y in [(865,300),(1000,300),(935,450)]:
        person(ax,x,y,TEAL,1.1)
    text(ax,935,565,"GROUP CHAT",size=31,bold=True,align="center")
    card(ax,220,690,760,115,LIME)
    text(ax,600,750,"Keep it out.",size=43,bold=True,align="center")
    save(fig,"private-stays-private","A sealed private envelope is blocked from reaching a group chat.")


def feedback():
    fig,ax=scene()
    for x,broken in [(70,False),(655,True)]:
        window(ax,x,100,475,375,"example app")
        card(ax,x+35,205,405,62,PAPER,radius=10)
        for y,w in [(300,290),(330,220)]:
            ax.plot([x+40,x+w],[y,y],color="#d5dfd3",linewidth=12,solid_capstyle="round")
        card(ax,x+105,365,265,85,LIME)
        text(ax,x+238,408,"Save",size=32,bold=True,align="center")
        if broken:
            ax.add_patch(Polygon([[x+330,432],[x+354,502],[x+368,477],[x+397,475]],facecolor=INK))
            cross(ax,x+410,405,.7)
        else:
            check(ax,x+412,408,.7)
    text(ax,308,535,"WORKS",size=28,bold=True,align="center",color=TEAL)
    text(ax,892,535,"BROKEN",size=28,bold=True,align="center",color=CORAL)
    bubble(ax,185,650,820,150,"Save fails in this version.",LIME,33)
    arrow(ax,(1020,675),(1090,490),TEAL)
    check(ax,980,815,.85)
    save(fig,"spot-the-fault","Two versions of an app have a Save button, but one is broken. Useful feedback points to that broken version and reports that Save fails.")


def coverage():
    fig,ax=scene()
    text(ax,75,100,"455",size=83,bold=True)
    text(ax,420,112,"papers",size=40)
    for i in range(455):
        col,row=i%35,i//35
        color=TEAL if i<428 else CORAL if i<431 else "#cdd5ca"
        ax.add_patch(plt.Rectangle((80+col*30,230+row*25),19,16,facecolor=color,edgecolor="none"))
    for x,count,label,color in [(80,"428","Full text",TEAL),(485,"3","Partial",CORAL),(850,"24","Abstract",GRAY)]:
        text(ax,x,690,count,size=52,bold=True,color=color)
        text(ax,x,775,label,size=28)
    save(fig,"paper-coverage","455 papers: 428 with full text, 3 partial or protocol-only, and 24 abstract-only.")


if __name__=="__main__":
    with (ROOT.parent/"bibliography/papers.csv").open(encoding="utf-8") as source:
        counts=Counter(row["read_depth"] for row in csv.DictReader(source))
    assert counts=={"full text":428,"partial text":3,"abstract only":24}
    for draw in (testing,update,minority,privacy,feedback,coverage):
        draw()
    print("Rendered six scenes; bibliography counts and text bounds checked.")
