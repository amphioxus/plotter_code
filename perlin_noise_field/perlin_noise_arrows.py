#!/usr/bin/env python

"""
A script to produce a 2D field of flow vectors aligned using Perlin Noise

* Can export to SVG file
* Can export to GCode for plotting. Parameters need to be adjusted to fit one's plotter)

"""
import math
import svgwrite
import numpy as np
try:
    import svgwrite
    from svgwrite import cm, mm 
except ImportError:
    print('svgwrite module needs to be installed.')
    print('https://github.com/mozman/svgwrite')
try:
    from noise import pnoise2, snoise2
except ImportError:
    print('Noise module needs to be installed.\nSee: ')
    print('https://github.com/caseman/noise')


#############################################################
#%%  SET PARAMETERS HERE:
draw_svg=True
export_gcode=False
octaves = 1
lacunarity=2.0
offset = (20,20) # where on the plotter bed should we start?
stepsize=5
height = 250
width = 100
arrowlength=3
tiplength=.20 # relative length of arrow tips (rel. to arrowlength). No tip if zero
border = 2*arrowlength # border for boundary box


# file names for export
fn='arrow_field-f{}-lac{}_{}x{}_{}step.svg'.format(octaves, lacunarity, width, height, stepsize)
fngc='arrow_field-f{}-lac{}_{}x{}_{}step.gcode'.format(octaves, lacunarity, width, height, stepsize)
#############################################################

def save_gcode_to_file(gc_str, fn):
    with open(fn, 'w') as f:
        f.write(gc_str)
    print('Saved to file {}'.format(fn))

def draw_svg_rectangle(dwg, ul, w, h, border):
    rlines = dwg.add(dwg.g(id='rlines', stroke='black'))
    
    pt1 = (ul[0]-border,   ul[1]-border)
    pt2 = (ul[0]-border,   ul[1]+h+border)
    pt3 = (ul[0]+w+border, ul[1]+h+border)
    pt4 = (ul[0]+w+border, ul[1]-border)
    rlines.add( dwg.line(start = (pt1[0]*mm, pt1[1]*mm), 
                        end   = (pt2[0]*mm, pt2[1]*mm) ) )
    rlines.add( dwg.line(start = (pt2[0]*mm, pt2[1]*mm), 
                        end   = (pt3[0]*mm, pt3[1]*mm) ) )
    rlines.add( dwg.line(start = (pt3[0]*mm, pt3[1]*mm),
                        end   = (pt4[0]*mm, pt4[1]*mm) ) )
    rlines.add( dwg.line(start = (pt4[0]*mm, pt4[1]*mm),
                        end   = (pt1[0]*mm, pt1[1]*mm) ) )
                        
def get_gcode_rectangle(ll, w, h, border, pendown, penup, s0=3000, s1=1000):
    """Gcode to draw a w*h rectange that corresponds to svg file
    coordinates. 
    s0 and s1 are feed rates for G0 and G1 commands, respectively.
    """
    # Goto point ll first:
    gcode='\n;Draw bounding box rectangle\n'
    gcode+="G0 F{} X{}Y{}\n".format(s0, ll[0]-border, ll[1] - border)
    # now start drawing (ccw):
    gcode+=pendown
    gcode+="G1 F{} X{}Y{}\n".format(s1, ll[0]-border, h-ll[1]+border)
    gcode+="G1 F{} X{}Y{}\n".format(s1, ll[0]+w+border, h-ll[1]+border)
    gcode+="G1 F{} X{}Y{}\n".format(s1, ll[0]+w+border, ll[1]-border)
    gcode+="G1 F{} X{}Y{}\n".format(s1, ll[0]-border, ll[1]-border)
    gcode+=penup
    
    return gcode
    
    
class Arrow(object):
    """Describes an arrow with 4 points. An arrow is set up by specifying:
    * Position of point a
    * Arrow length (a->b)
    * Direction of line a->b in space (dir)
    
    
             c
              \
    a----------b
              /
             d
             
    If tiplength is set <= zero, a simple line a->b is produced.
    """
    arrow_id = 0
    g0_speed = 4000 # mm/min for fast positioning moves
    g1_speed = 1000 # mm/min for pen motion
    
    def __init__(self, a, length=1, dir=0, tiplength=0.25, reltips=True):
        """Initialize the Arrow Object
        
        Keyword arguments:
        a -- start point
        length -- a->b in mm
        dir -- direction of arrow in degrees
        tiplength -- if reltips==True, the tiplength is a fraction of length a->b, 
                   otherwise it's length in mm
        reltips -- if set to False, tiplength is in mm
                   
        """
        self.a = np.array( [a[0], a[1] ])
        R = self.get_rotation_matrix( dir )
        b = np.array([length, 0])
        self.b = self.a + b.dot(R)
        #self.b = np.array( [b[0], b[1] ])
        self.v = self.b - self.a
        self.length = length
        if tiplength > 0:
            self.maketips(angle=140,
                          tiplength=tiplength,
                          relative=reltips)
            self.hastip = True
        else:
            self.hastip = False
        
    def get_rotation_matrix(self, deg=130):
        theta = np.radians(deg)
        c, s = np.cos(theta), np.sin(theta)
        return np.array(((c,-s), (s, c))) # rotation matrix
        
    def maketips(self, angle=140, tiplength=0.2, relative=True):
        """Draws the tips if tiplength > 0"""
        if relative:
            l = self.length * tiplength
        else:
            l = tiplength
        v = self.v / self.length * l
        v_rot = v.dot(self.get_rotation_matrix(angle))
        self.c = self.b + v_rot
        v_rot = v.dot(self.get_rotation_matrix(-angle))
        self.d = self.b + v_rot
        
    def draw_to_svg(self, dwg):
        """Draws the arrow into an svgwrite.Drawing object (dwg), using mm as units
        Note: Native origin of SVG is upper left, but for plotter it's lower left.
        """
        alines = dwg.add(dwg.g(id='hlines', stroke='black'))
        alines.add( dwg.line(start = (self.a[0]*mm, self.a[1]*mm), 
                             end   = (self.b[0]*mm, self.b[1]*mm)))
        if self.hastip:
            alines.add( dwg.line(start = (self.b[0]*mm, self.b[1]*mm), 
                                 end   = (self.c[0]*mm, self.c[1]*mm)))
            alines.add( dwg.line(start = (self.b[0]*mm, self.b[1]*mm), 
                                 end   = (self.d[0]*mm, self.d[1]*mm)))
        
    def gcode_draw_arrow(self, pendown="", penup="", img_height=0):
        """Returns a string of gcode to draw arrow at its coordinates.
        Assumes we are in the same coordinate system as the arrow.
        If img height is specified, everything is flipped along 
        horizontal axis (to make svg and gcode origin consistant)
        """
        if img_height:
            # flip all the points along horizontal axis so 
            # gcode output looks like the svg image
            ay = img_height - self.a[1]
            by = img_height - self.b[1]
            cy = img_height - self.c[1]
            dy = img_height - self.d[1]
        else:
            ay = self.a[1]
            by = self.b[1]
            cy = self.c[1]
            dy = self.d[1]
            
        gcode = ''
        # first draw a->b
        gcode += "G0 F{} X{} Y{} Z0\n".format(g0_speed, self.a[0], ay)
        gcode += pendown
        gcode += "G1 X{} Y{} Z0\n".format(self.b[0], by)
        gcode += penup
        if self.hastip:
            # now draw c->b->d
            gcode += "G0 F{} X{} Y{} Z0\n".format(g0_speed, self.c[0], cy)
            gcode += pendown
            gcode += "G1 F{} X{} Y{} Z0\n".format(g1_speed, self.c[0], cy)
            gcode += "G1 X{} Y{} Z0\n".format(self.b[0], by)
            gcode += "G1 X{} Y{} Z0\n".format(self.d[0], dy) 
            gcode += penup
        gcode += "\n"
        
        return gcode

def main():
    if (width % stepsize) or (height % stepsize):
        raise ValueError('Width and height need to be evenly divisible by stepsize.')
    
    W = int(width/stepsize)+1
    H = int(height/stepsize)+1

    freq = 16.0 * octaves
    angles = []
    max_angle = 180
    # collect angles for 2D arrow field into a list:
    for y in range(0,H):
        for x in range(0,W):
            nraw=snoise2(x / freq,
                         y / freq,
                         octaves,
                         lacunarity=lacunarity)
            n = int(nraw * max_angle-1 + max_angle)
            angles.append( n )
    print('Angles: n = {}'.format(len(angles)))
    # Export as SVG file:

    if draw_svg:
        dwg = svgwrite.Drawing(filename=fn,
                                size=( "{}mm".format(width+2*offset[0]+border), 
                                        "{}mm".format(height+2*offset[1]+border)),
                                viewbox=(0,0, width+2*offset[0]+border, 2*height+offset[1]+border),
                                debug=False)
        # place arrows, using angle values from above    
        c=0
        # for y in range(offset[1], height+2*offset[1], stepsize):
        #     for x in range(offset[0], width+2*offset[0], stepsize):
        for yt in range(0, H):
            for xt in range(0, W):
                x = xt*stepsize + offset[0]
                y = yt*stepsize + offset[1]
                a = Arrow((x,y), length=arrowlength, dir=angles[c], tiplength=tiplength)
                a.draw_to_svg(dwg)
                c+=1
        if border:
            # draw_svg_rectangle(dwg, ul, w, h, border)
            draw_svg_rectangle(dwg, offset, width, height, border)
        dwg.save()
        print('Saved to SVG file: {}'.format(fn))
    
    # Create gcode of arrow field if flag is set:
    if export_gcode:
        # some gcode before actual drawing happens:
        pen_down = "M3 S10\nG4 P0.5; Pen down\n"
        pen_up = "M3 S120\nG4 P0.5; Pen up\n"
        g0_speed = 4000 # mm/min for fast positioning moves
        g1_speed = 1000 # mm/min for pen motion
        gcode_string = """
    ; GCODE Generated by Python script perlin_noise_arrows.py
    ; Perlin noise field
    G21; mm-mode
    G54; Work Coordinates
    G21; mm-mode
    G90; Absolute Positioning
    ; Plotter Mode Active
    M3 S120; pen up
    G0 Z0
    G0 F{s0} X{x} Y{y}; go to {x}/{y}
    G1 F{s1}; speed when plotting

    """.format( x=offset[0], 
                y=offset[1],
                s1=g1_speed,
                s0=g0_speed)
        draw_arrows=True # debug
        if draw_arrows:
            # Now draw the arrow objects:
            c=0
            for y in range(offset[1],height+2*offset[1], stepsize):
                for x in range(offset[0],width+2*offset[0], stepsize):
                    a = Arrow((x,y), 
                              length=arrowlength, 
                              dir=angles[c], 
                              tiplength=tiplength)
                    a.g0_speed=g0_speed
                    a.g1_speed=g1_speed
                    gcode_string += a.gcode_draw_arrow( pen_down, 
                                                        pen_up,
                                                        img_height=height+2*offset[1])
                    c+=1
            
        if border:
            # draw a box around our arrow field
            gcode_string += get_gcode_rectangle((offset[0], offset[1]),
                                                 width,
                                                 height+2*offset[1],
                                                 border,
                                                 pen_down,
                                                 pen_up)
        
        # go back home with pen raised
        gcode_string += "G0 F{} X0 Y0; go to 0/0".format(g0_speed)
    
        save_gcode_to_file(gcode_string, fngc)
        print('Exported gcode. File: '+fngc)
    

if __name__=="__main__":
    main()
    
    