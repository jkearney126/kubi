"""
Run ``pip install .`` (or ``pip install -e .`` for editable mode)
which will install the command ``kubi`` inside your current environment.
"""

import argparse
import logging
import sys
import os
import glob
import numpy as np
from numpy import pi

from kubi import __version__

__author__ = "Keim, Stefan"
__copyright__ = "Keim, Stefan"
__license__ = "MIT"

_logger = logging.getLogger(__name__)


# ---- Python API ----
# The functions defined in this section can be imported by users in their
# Python scripts/interactive interpreter, e.g. via
# `from kubi.kubi import kubi`,
# when using this Python module as a library.


def kubi(args):
    os.environ['PATH'] =  'C:/Program Files/vips-dev-8.10/bin' + ';' + os.environ['PATH']

    if args.vips:
        os.environ['PATH'] = args.vips + ';' + os.environ['PATH']
    
    import pyvips
    
    src_names = None
    if args.ii == None:
        _logger.info('Generating index')

        size = -1
        if args.size:
            size = args.size
        elif args.src:
            src_names = glob.glob(args.src,recursive=True)
            src_count = len(src_names)
            src_multi = src_count > 1

            if src_count == 0:
                print(f'{args.src}: No such file or directory')
                return
            for name in src_names:
                image = pyvips.Image.new_from_file(name)
                size = max(size, int(image.width / 4))


        ### TODO replace numpy with vips

        ls = np.linspace(-1, 1, size, dtype="f4", endpoint=False)
    
        if args.transform == "eac": # C.Brown (2017): Bringing pixels front and center in VR video
            ls = np.tan(ls / 4 * pi)
        elif args.transform == "otc": # M.Zucker & Y.Higashi (2018): Cube-to-sphere Projections for Procedural Texturing and Beyond
            ls = np.tan(ls * 0.8687) / np.tan(0.8687)

        xv,yv = np.meshgrid(ls, ls)

        xv2 = xv ** 2
        yv2 = yv ** 2
 
        idx = np.stack([
            np.arctan(xv),                      #tha0
            np.arctan2(yv, np.sqrt(1 + xv2)),   #phi0
            np.arctan2(xv, yv),                 #tha1
            np.arctan2(1, np.sqrt(yv2 + xv2))   #phi1
        ], axis=-1) 
    
        ### end of numpy

        ls = xv = yv = xv2 = yv2 = None
        
        idx = pyvips.Image.new_from_memory(idx.reshape(size**2 * 4), size, size, 4, 'float') / (pi/2)

        idx = [
            pyvips.Image.bandjoin(idx[0]+3,idx[1]+1),
            pyvips.Image.bandjoin(idx[0]+1,idx[1]+1),
            pyvips.Image.bandjoin((idx[2]-2)%4,1-idx[3]),
            pyvips.Image.bandjoin((4-idx[2])%4,1+idx[3]),
            pyvips.Image.bandjoin(idx[0]+2,idx[1]+1),
            pyvips.Image.bandjoin(idx[0]%4,idx[1]+1),
        ]

        if args.layout is None or args.layout in ("column","row"):
            if args.inverse is not None:
                for f in range(6):
                    idx[f] = idx[f].rot180() if args.inverse == 'both' else idx[f].flip(args.inverse)
            
            if args.layout is None:
                index = None
                idxA = idx
            else:
                index = pyvips.Image.arrayjoin(idx, across=6 if args.layout == "row" else 1)
        else:
            s0 = 0
            s1 = size
            s2 = s1*2
            s3 = s1*3
            s4 = s1*4

            if args.layout == "crossL":
                index = pyvips.Image.black(s4, s3, bands = 2)
                index -= 1.0
                index = index.insert(idx[1],s0,s1)
                index = index.insert(idx[4],s1,s1)
                index = index.insert(idx[0],s2,s1)
                index = index.insert(idx[5],s3,s1)
                index = index.insert(idx[2],s1,s0)
                index = index.insert(idx[3],s1,s2)
            elif args.layout == "crossR":
                index = pyvips.Image.black(s4, s3, bands = 2)
                index -= 1.0
                index = index.insert(idx[5],s0,s1)
                index = index.insert(idx[1],s1,s1)
                index = index.insert(idx[4],s2,s1)
                index = index.insert(idx[0],s3,s1)
                index = index.insert(idx[2],s2,s0)
                index = index.insert(idx[3],s2,s2)
            elif args.layout == "crossH":
                index = pyvips.Image.black(s3, s4, bands = 2)
                index -= 1.0
                index = index.insert(idx[1],s0,s1)
                index = index.insert(idx[4],s1,s1)
                index = index.insert(idx[0],s2,s1)
                index = index.insert(idx[5].rot180(),s1,s3)
                index = index.insert(idx[2],s1,s0)
                index = index.insert(idx[3],s1,s2)

            if args.inverse is not None:
                index = index.rot180() if args.inverse == 'both' else index.flip(args.inverse)
        
        if args.io is not None:
            idx = idx[0].bandjoin(idx[1:6]) if index is None else index
            idx.tiffsave(args.io, compression="lzw", predictor="float")
                
    else: #args.ii != None
        _logger.info(f'Reading index: {args.ii}')

        idx = pyvips.Image.tiffload(args.ii)
        if idx.bands == 12:
            index = None
            idxA = [idx[0:2], idx[2:4], idx[4:6], idx[6:8], idx[8:10], idx[10:12]]
        else:
            index = idx

    idx = None

    if args.src:
        if src_names is None:
            src_names = glob.glob(args.src, recursive=True)
            src_count = len(src_names)
            src_multi = src_count > 1

        dst_suffix = '_'+ args.transform
        dst_folder = dst_name = dst_ext = None 

        # define dst defaults for single and multi src
        if args.dst:
            name_split = os.path.splitext(os.path.basename(args.dst))
            dst_name = name_split[0]
            dst_suffix = f'_{name_split[0]}' if name_split[0] != '' and src_multi else ''
            dst_ext = name_split[1]
            dst_folder = os.path.dirname(args.dst)
            dst_folder = dst_folder if dst_folder else '.'

            if not os.path.exists(dst_folder):
                os.makedirs(dst_folder)
        
        interp = pyvips.vinterpolate.Interpolate.new(args.resample)

        # START LOOP on src files
        for name in src_names:
            img = pyvips.Image.new_from_file(name)
            name_split = os.path.splitext(os.path.basename(name))

            if not dst_folder:
                dst_folder = os.path.dirname(name)
                dst_folder = dst_folder if dst_folder else '.'

            if not dst_name or src_multi:
                dst_name = name_split[0]

            if not dst_ext:
                dst_ext = name_split[1]

            dst = f'{dst_folder}/{dst_name}{dst_suffix}'
        
            fac = img.width/4

            
            if index is None:
                for f in range(6):
                    idx = idxA[f]*fac
                    fn = args.facenames[f] if args.facenames is not None else str(f)
                    mapim = img.mapim(idx, interpolate=interp)
                    mapim.write_to_file(f'{dst}_{fn}{dst_ext}', **args.co)
            else:
                idx = index*fac
                mapim = img.mapim(idx, interpolate=interp)
                mapim.write_to_file(f'{dst}{dst_ext}', **args.co)
                


# ---- CLI ----
# The functions defined in this section are wrappers around the main Python
# API allowing them to be called directly from the terminal as a CLI
# executable/script.


def parse_args(args):
    parser = argparse.ArgumentParser(description="cubemap generator")
    parser.add_argument(
        "--version",
        action="version",
        version="kubi {ver}".format(ver=__version__),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO,
    )
    parser.add_argument(
        "-q",
        "--quite",
        dest="loglevel",
        help="set loglevel to ERROR",
        action="store_const",
        const=logging.ERROR,
    )
    parser.add_argument(dest="src", help="the input glob pattern", metavar="srcfile", nargs='?' )
    parser.add_argument(dest="dst", help='the output file or folder', metavar="dstfile", nargs='?')
    parser.add_argument('-s', '--size ', dest="size", metavar='<int>', type=int, help='the edge size (default 1/4 of max src width)')
    parser.add_argument('-t', '--transform', choices=['eac', 'otc'], help=""" 
      eac: Equi-angular cubemap;
      optan: optimized tangent transform
    """)
    parser.add_argument('-i', '--inverse', choices=['horizontal', 'vertical', 'both'], help="flips the idx")
    parser.add_argument('-l', '--layout ', dest="layout", choices=['row', 'column', 'crossL', 'crossR', 'crossH'], help="""
      none: seperate faces (default);
      row: +X,-X,+Y,-Y,+Z,-Z;
      column: +X,-X,+Y,-Y,+Z,-Z;
      crossL: vertical cross with +Y,-Y on the left;
      crossR: vertical cross with +Y,-Y on the right;
      crossH: horizontal cross;
    """)
    parser.add_argument('-r', '--resample', default='bilinear', choices=['nearest', 'bilinear', 'bicubic', 'lbb', 'nohalo', 'vsqbs'], help="""
      nearest: nearest-neighbour interpolation;
      bilinear: bilinear interpolation (default);
      bicubic: bicubic interpolation (Catmull-Rom);
      lbb: reduced halo bicubic;
      nohalo: edge sharpening resampler with halo reduction;
      vsqbs: B-Splines with antialiasing smoothing
    """)
    parser.add_argument('-f', '--facenames', metavar="<str>", nargs=6 ,help='suffixes for +X, -X, +Y, -Y, +Z, -Z (e.g. -n r l u d f b)')
    parser.add_argument('-co', dest='co', metavar='<NAME=VALUE>*', action='append',  help='create options (more info in the epilog)')
    parser.add_argument('--vips', help='path to the VIPS bin directory (usefull if VIPS is not added to PATH; e.g. on Windows)')
    parser.add_argument('--io', dest='io', help='index file output', metavar='dstindex')
    parser.add_argument('--ii', dest='ii', help='index file input', metavar='srcindex')

    args = parser.parse_args(args)

    if args.src is None:
        if args.io is None:
            parser.print_usage(sys.stderr)
            print(f"{__name__}: error: 'srcfile' or 'dstindex' has to be set")
            return
        elif args.size is None:
            parser.print_usage(sys.stderr)
            print(f"{__name__}: error: to write 'dstindex' without 'src' you have to set 'size' (-s)")
            return
    
    if args.ii is not None and not (all(v is None for v in [args.size,args.transform,args.inverse,args.layout])):
        parser.print_usage(sys.stderr)
        print(f"{__name__}: error: 'size', 'transform', 'flip' and 'layout' is already baked into the 'srcindex'; please remove the arguments")
        return

    if args.transform is None:
        args.transform='cubemap'

    coDict = {}
    if args.co:
        for co in args.co:
            cosp = co.split("=", 1)
            if len(cosp) == 2:
                coDict[cosp[0]] = int(cosp[1]) if cosp[1].isnumeric() else cosp[1]
            else:
                coDict['compression'] = cosp[0]
    args.co = coDict

    return args


def setup_logging(loglevel):
    logging.getLogger("pyvips").setLevel(logging.ERROR)
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def main(args):
    args = parse_args(args)
    if args is None: return
    setup_logging(args.loglevel)
    kubi(args)


def run():
    main(sys.argv[1:])


if __name__ == "__main__":
    # ^  This is a guard statement that will prevent the following code from
    #    being executed in the case someone imports this file instead of
    #    executing it as a script.
    #    https://docs.python.org/3/library/__main__.html
    run()