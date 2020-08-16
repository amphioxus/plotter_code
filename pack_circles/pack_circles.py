#!/usr/bin/env python3

"""
Progam to fill white or black areas in an input mask image with circles of varying radii.
(--r_min and --r_max control the range of allowed radii.)

No optimization when testing for circle overlap. Each circle tests every other one, so this
gets very slow when using 1000+ circles.

Radii are created so that small ones are prefered:

    # Float radii instead of integer radius
    r_min = 10
    r_max = 30
    nradii = (r_max-r_min) * 10 # how many distinct radii to pick from
    n = 5000
    rpool = [random.uniform(r_min, r_max) for i in range(0,nradii)]
    rpool.sort(reverse=False)

    rpool = np.array(rpool)
    # make a probability function to skew towards smaller radii
    x = np.linspace(r_min, r_max, len(rpool))
    k = -20
    p = k*x
    p = p + abs(min(p))+5
    p = p / np.sum(p) # normalize so sum is one

    radii = np.random.choice(rpool, size=n, p=p)

    # Show histogram of radii:
    # rs = np.random.choice(x, size=500, replace=True, p=y)
    plt.subplot(221)
    plt.plot(x,p)
    plt.subplot(222)
    plt.hist(radii)
    plt.xlabel('Radius')
    plt.ylabel('N')



Armin H. / 8-15-2020
"""


import argparse
import os
import time
import numpy as np
import random
import matplotlib
from matplotlib import pyplot as plt
# non-standard modules:
try:
    import cv2
except ImportError:
    raise ImportError('This script needs OpenCV to work. https://opencv.org/')
try:
    import svgwrite
except ImportError:
    raise ImportError('This script needs the svgwrite module to work. https://pypi.org/project/svgwrite/')
    
    
class Circle(object):
    """
    Defines a circle
    """
    def __init__(self, center, r, offset=0):
        self.center  = center
        self.x = int(center[0])
        self.y = int(center[1])
        self.radius = int(r)
        self.offset = offset # additional distance between circles
        
    def overlaps_other(self, other):
        """Determine if this circle instance overlapse the other"""
        c1c2 = np.sqrt( (self.x - other.x)**2 + (self.y - other.y)**2 )
        return c1c2 < (other.radius+self.radius + self.offset) 
        
    def is_inside_mask(self, maskimg):
        """Determine if it falls within mask boundary. True if it falls
        totally within the mask's allowed area"""
        # Build mask with circle on it
        circlemask = np.zeros(maskimg.shape, dtype=np.uint8)
        cv2.circle(circlemask, (self.x, self.y), self.radius, (255, 255, 255), -1, 8, 0)
        # Apply mask (using bitwise & operator)
        result_array = maskimg & circlemask
        # If circlemask and result_array have same pixel sum, the full circle has space enough
        if np.sum(circlemask) == np.sum(result_array):
            return True
        else:
            return False
    
class CircleCloud(object):
    """
    Defines a collection of n circles, placed on an image mask.
    img_fn ... file name of input image mask
    n ... number of circles to place
    If invert_mask is set to True: circles are drawn on black areas of input image.
    """
    def __init__(self, maskimg_fn, n=100, invert=False, verbose=True):        
        
        self.n = n
        self.max_attempts = 100 # how often should we try to place a circle?
        self.verbose = verbose
        self.maskupdate = False
        self.offset = 0 # extra distance between circles
        self.circles = []
        maskimg_gray = cv2.imread(maskimg_fn, 0)
        # binary threshold
        (thresh, self.maskimg) = cv2.threshold(maskimg_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        if invert:
            self.maskimg = cv2.bitwise_not(self.maskimg)
        self.height, self.width = self.maskimg.shape
        # coordinates where mask is white:
        yvals, xvals = np.where(self.maskimg == 255)
        self.maskcoords = np.array(list(zip(xvals,yvals)))
    
    def update_mask_coordinates(self):
        """Add currently existing circles to the mask, and reduce space where new
        circles can be placed. This does not improve anything when just using a few
        hundred points. Still need testing whether it leads to any speed improvements
        at all. For most tests, it's actually slower...
        """
        print('updating mask')
        tmp_mask = self.maskimg.copy()
        for c in self.circles:
            cv2.circle( tmp_mask, (c.x, c.y), c.radius, (255, 255, 255), -1, 8, 0)
        self.maskimg = tmp_mask
        yvals, xvals = np.where(tmp_mask == 255)
        self.maskcoords = np.array(list(zip(xvals,yvals)))
        
    def place_circles(self, r_min, r_max):
        # uniform probability for all radii:
        #radii = [random.randrange(r_min, r_max+1) for i in range(0, self.n)] # random integers between r min and r max
        # probability of radii skewed towards smaller ones:
#         x = np.arange(r_min, r_max+1, 1) # for integer radii only
        nradii = int( (r_max-r_min) * 10 ) # how many distinct radii to pick from
        rpool = [random.uniform(r_min, r_max) for i in range(0, nradii)]
        rpool.sort(reverse=False)
        rpool = np.array(rpool)
        # make a probability function to skew towards smaller radii
        x = np.linspace(r_min, r_max, len(rpool))
        p = -20*x
        p = p + abs(min(p))+5 # shift p values > 0
        p = p / np.sum(p) # normalize so sum is one
        
        radii_tmp = np.random.choice(rpool, size=self.n, p=p)
        radii_tmp.sort() # plot large circles first
        radii = radii_tmp[::-1] # reverse sorted array
        c = 0 # counter for circles
        a = 0 # count attempts for each circle
        while c < self.n:
            if a > self.max_attempts:
                if self.verbose:
                    print('Giving up with circle {}. Trying next circle radius'.format(c))
                a = 0 # reset attempt count for next loop
                c += 1 # skip to next one
                continue
            if self.verbose:
                print('Placing cirle {}'.format(c))
                
            # Every once in a while, update allowed coordinates
            if  a == 0 and c%100 == 0:
                print('circle #{}'.format(c))
                if c>0 and self.maskupdate:                    
                    self.update_mask_coordinates()
                
            # pick a random coordinate from the allowed ones
            circle = Circle( center = self.maskcoords[ random.randrange(0, len(self.maskcoords)) ],
                             r = radii[c],
                             offset=self.offset)
            # check if pick is totally within mask:
            if circle.is_inside_mask(self.maskimg): 
                # it also must not overlap any previously placed circle:
                overlaps = []
                for othercircle in self.circles:
                    overlaps.append( circle.overlaps_other(othercircle) )                    
                if not any(overlaps):
                    if self.verbose:
                        print('Circle added') # debug message
                    self.circles.append(circle)
                    c += 1
                    a = 0 # reset attempt count
                else:
                    if self.verbose:
                        print('Overlaps')
                    a += 1 # keep attempting
                    continue
            else:
                a += 1
                if self.verbose:                    
                    print('Circle does not fit mask (attempt {})'.format(a)) # debug message
                continue   
    
    def draw_svg(self, outfn='circles.svg'):
        """Go through each circle in the cloud and draw an svg circle for it.
        Todo: Scale to new width/height of svg output.
        """        
        fname, fext = os.path.splitext(outfn)
        if not fext.endswith('.svg'):
            print('File name needs to end in ".svg"')
            print('Changed "{}" to "{}"'.format(outfn, fname+'.svg'))
            outfn = fname+".svg"
        dwg = svgwrite.Drawing(outfn, profile='tiny')
        # background rectangle
        dwg.add(dwg.rect((0,0),(self.width, self.height),fill='black' ))
        for c in self.circles:
            dwg.add(dwg.circle(center=(c.x, c.y),
                    r=c.radius, 
                    stroke=svgwrite.rgb(15, 15, 15, '%'),
                    fill='white'))
        dwg.save()
#         if self.verbose:
        print('SVG file saved as: {}'.format(outfn))
    
    
def run(args):
    fname = args.input[0] # input file name (png mask)
    n = args.n_points
    fnamebase = os.path.basename(fname)
    outbase, ext = os.path.splitext(fnamebase)
    # determine output file name (svg)
    if not args.output:
        fout = 'circles_{}_ma-{}_n-{}.svg'.format(outbase,
                                   args.max_attempts, 
                                   n)
    else:
        b, ext = os.path.splitext(args.output)
        if not ext.endswith('.svg'):
            fout = b+'.svg'
        else:
            fout = args.output              
    
    print('Input file: {}'.format(fname))
    print('Attempting to place {} circles on mask image.'.format(n))
    print('Number of attempts for each circle: {}'.format(args.max_attempts))
    print('Offset (min distance between circles): {}'.format(args.offset))
    print('Output file: {}'.format(fout))
    start = time.time()
    
    cc = CircleCloud(fname, 
                     n=n, 
                     verbose=args.verbose,
                     invert=args.invert)
    cc.max_attempts = args.max_attempts
    cc.offset = args.offset
    cc.maskupdate = args.update
    cc.place_circles(args.r_min, args.r_max)
    
    end = time.time()
    elapsed = end - start
    
    cc.draw_svg(fout)
    print('Time elapsed: {:.2f} seconds'.format(elapsed))
    
def parse_args():
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('input', nargs=1, 
                        help='Input mask file. (Binary PNG: white and black areas.) '\
                        'By default, circles are drawn on white areas. '\
                        'Use -i option to invert and draw on black')
    PARSER.add_argument("-o", "--output", help="Output file name (.svg)")
    PARSER.add_argument("-n", "--n_points", 
                        help="How many circles to draw (attempt)", 
                        default=300, type=int)
    PARSER.add_argument("--r_min", 
                        help="Minimum radius", 
                        default=2., type=float)    
    PARSER.add_argument("--r_max", 
                        help="Maximum radius", 
                        default=15., type=float)                                                
    PARSER.add_argument("-m", "--max_attempts", 
                        help="How many attempts when placing each circle.", 
                        default=100, type=int)
    PARSER.add_argument("--offset", 
                        help="Extra pixel distance between circles.", 
                        default=0, type=float)                                
    PARSER.add_argument("-u", "--update", 
                        help="Update mask from time to time to remove areas with already placed circles.", \
                        action="store_true")                                         
    PARSER.add_argument("-i", "--invert", 
                        help="Invert the mask so that circles are painted on black areas.", \
                        action="store_true")
    PARSER.add_argument("-v", "--verbose", 
                        help="Be extra verbose when running the program.", \
                        action="store_true")                        
    return PARSER.parse_args()
    
    
if __name__ == "__main__":
    args = parse_args()
    run(args)
    
    
    