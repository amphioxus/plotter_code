#!/usr/bin/env python3

"""
Experimenting with lines: noisily offset vertical lines 

Using Cairo to draw to SVG (pycairo bindings: https://pycairo.readthedocs.io/en/latest/index.html)
Uses svg-to-gcode library (https://pypi.org/project/svg-to-gcode/) to make gcode for plotter

"""
import sys
try:
    # from svg_to_gcode.svg_parser import parse_file
    from svg_to_gcode.compiler import Compiler, interfaces
    # from svg_to_gcode.formulas import linear_map
    from svg_to_gcode import geometry as geom
except:
    print("This example code depends on the svg_to_gcode library.")
    print("See: https://pypi.org/project/svg-to-gcode/")
    print("Install with pip: `pip install svg-to-gcode`")
    sys.exit(0)

import matplotlib
from matplotlib import pyplot as plt

import numpy as np
import random


# The OffsettableLine() class provides a way to define a line, and then to
# create copies of the original line that have an x-axis offset, as well
# as some added noise. It can return a `LineSegmentChain`, which the parser
# interface can use to generate gcode.
class CustomPenPlotterInterface(interfaces.Gcode):
    """
    A custom interface for the Acro 55, using a servo-controlled
    pen holder.
    """
    def __init__(self, pen_up=270, pen_down=70):
        super().__init__()
        self.pen_up = pen_up
        self.pen_down = pen_down
        # self.fan_speed = 1

    # Override the laser_off method to lift the pen.
    def laser_off(self):
        return f"M3 S{self.pen_up}; Pen up\nG4 P0.5; Pause"  # Lift the pen and wait a bit

    # Override the set_laser_power method (power ignored, only used to lower the pen)
    def set_laser_power(self, power):
        if power < 0 or power > 1:
            raise ValueError(f"{power} is out of bounds. Laser power must be given between 0 and 1. "
                             f"The interface will scale it correctly.")
        return f"M3 S{self.pen_down}; Pen down\nG4 P0.5; Pause"  # Drop the pen, ignore laser power


class OffsettableLine(object):
    """Defines one line that can create an offset version of itself
    The offset() method returns a new line object, offset in the x direction
    by a certain amount +/- noise
    """
    def __init__(self, x, y, color='red', thickness=1) -> None:
        """ _x is list of x coordinates, _y of corresponding y coords"""
        self._x = x
        self._y = y
        self._color = color
        self._thickness = thickness

    def offset(self, offset, dist=.5, color='gray', clip=0, shrink=0):
        """return an x-offset copy of the line"""
        nx = [i+offset+ dist*random.random() for i in self._x]
        ny = self._y # y stays the same
        if clip:
            # remove n-clip points from left and right of arrays
            length = len(nx)
            nx = nx[0+clip:length-clip]
            ny = ny[0+clip:length-clip]
        if shrink:
            # shrink y dimension by a factor
            y_min = np.min(ny)
            y_max = np.max(ny)
            length = y_max-y_min # length of current line in y dimension
            ln = length * (1-shrink) # new length shrunk by factor
            d = (length - ln)/2
            ny = np.linspace( y_min+d, y_max-d, len(nx) )
        if len(nx):
            return OffsettableLine( x=nx, y=ny, color=color)
        else:
            return None

    def plot(self, ax=None, **kwargs):
        """Plot the line with Matplotlib"""
        if ax:
            ax.plot(self._x, self._y, color=self._color, **kwargs)
        else:
            plt.plot(self._x, self._y, color=self._color)


    def get_LineSegmentChain(self):
        """Return a LineSegmentChain from the svg_to_gcode geometry library"""
        points = [geom.Vector(p[0],p[1]) for p in zip(self._x, self._y)]
        lines = []
        n_points = len(points)
        for i,p in enumerate(points):
            if i < n_points-1:
                l = geom.Line( p, points[i+1] )
                lines.append(l)
        return geom.LineSegmentChain(lines)



def test_code():
    save_gcode=True
    gcode_fn = "offset_lines_example_200x310mm.gcode"
    # Create a curve for testing
    A=2
    B=8
    f1 = 2
    f2 = .5
    x = np.linspace(0,np.pi, 100)
    y1 = ( A * np.sin(2*f1*x) ) + A
    y2 =  ( B * np.sin(2*f2*x))
    y = y1 * y2
    # create a line object, with x and y coordinates switched so the line
    # we just created is rotated 90deg
    # scale the new y axis, so we end up in mm space
    x = 10 + ( x/max(x) * 190 )
    y = y + 10
    l = OffsettableLine( y, x, color='black')
    lines = [l] # initialize with orig. line
    # curves = [ l.get_LineSegmentChain() ]
    n_lines = 48 # how many offset lines to produce

    # incremental increase in offset
    d_offset = 0.15
    offsets = []
    n = 0.5
    # increase noise after each lie is offset
    nmax = 0.025
    d_noise = 0.1
    # precalculate noise maxima:
    noisemaxima = []
    for i in range(0,n_lines):
        n = n + d_offset
        offsets.append( n )
        nmax = nmax + d_noise
        noisemaxima.append( nmax )

    mymax=0.5
    myclip=0 # clip just clips off line at either end
    myshrink=0.0092 # shrink reinterpolates line to shrink it by factor
    imax = 0

    for i in range(0,n_lines):
        try:
            newline = lines[i].offset( offset=offsets[i],
                                    dist=noisemaxima[i],
                                    color='black', #'#dddddd',
                                    clip=myclip,
                                    shrink=myshrink)
        except:
            break
        lines.append( newline )
        if i >= imax:
            imax = i

    # Instantiate a compiler, specifying the custom interface and the speed at which the tool should move.
    gcode_compiler = Compiler(CustomPenPlotterInterface,
                            movement_speed=5000,
                            cutting_speed=1400,
                            pass_depth=1,
                            custom_footer=["G1 F4000 X0.0 Y0.0; go home"])
    # go through it in reverse order, so we start drawing the noisier lines first
    for l in reversed(lines):
        gcode_compiler.append_curves( l.get_LineSegmentChain() )

    if save_gcode:
        gcode_compiler.compile_to_file(gcode_fn)
        print(f"Saved example gcode output to: {gcode_fn}")

    fig, ax = plt.subplots(1, figsize=(12, 12))

    for l in lines:
        l.plot(ax=ax)

    ax.set_ylabel('y [mm]')
    ax.set_xlabel('x [mm]')
    ax.set_ylim(-10,310)
    ax.set_xlim(-10,310)

    plt.title('Plotter preview')
    plt.axis('square')
    fout = 'offset_lines_example.png'
    plt.savefig(fout)
    print(f"Saved example png output to: {fout}")
    # plt.show()


if __name__=="__main__":
    test_code()