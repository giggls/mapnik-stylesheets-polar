#!/usr/bin/python
#
# render data from postgresql to an tiles in an polar projection
#

from optparse import OptionParser
import sys, os, multiprocessing

try:
    import mapnik2 as mapnik
except:
    import mapnik

cairo_exists = True

try:
    import cairo
except ImportError:
    cairo_exists = False

def main():
    style = "/usr/share/osm-mapnik/osm.xml"
    dir = "tiles"
    type = "png"
    scale = 6000000
    minzoom = 1
    maxzoom = 6
    threads = multiprocessing.cpu_count() - 1
    
    parser = OptionParser()
    parser.add_option("-s", "--style", action="store", type="string", dest="style", 
                      help="path to the mapnik stylesheet xml, dmefaults to the openstreetmap default style: "+style)
    
    parser.add_option("-d", "--dir", action="store", type="string", dest="dir", 
                      help="path to the destination folder, defaults to "+type)
    
    parser.add_option("-t", "--type", action="store", type="string", dest="type", 
                      help="file type to render (png, png256, jpg), defaults to "+type)
    
    parser.add_option("-z", "--minzoom", action="store", type="int", dest="minzoom", 
                      help="minimum zoom level to render, defaults to "+str(minzoom))
    
    parser.add_option("-Z", "--maxzoom", action="store", type="int", dest="maxzoom", 
                      help="maximum zoom level to render, defaults to "+str(maxzoom))
    
    parser.add_option("-T", "--threads", action="store", type="int", dest="threads", 
                      help="number of threads to launch, defaults to "+str(threads)+" (CPUs-1)")
    
    (options, args) = parser.parse_args()
    if options.style:
        style = options.style
    
    if options.dir:
        dir = options.dir
    
    if options.type:
        type = options.type
    
    if options.minzoom:
        minzoom = options.minzoom
    
    if options.maxzoom:
        maxzoom = options.maxzoom
    
    
    if(options.threads > 1):
        queue = multiprocessing.JoinableQueue(32)
        lock = multiprocessing.Lock()

        renderers = {}
        for i in range(options.threads):
            renderer = RenderThread(i, queue, style, scale, dir, type, lock)
            render_thread = multiprocessing.Process(target=renderer.run)
            render_thread.start()
            renderers[i] = render_thread

        for z in range(minzoom, maxzoom+1):
            n = 2**z
            for x in range(0, n):
                for y in range(0, n):
                    t = (z, x, y)
                    queue.put(t)

        # Signal render threads to exit by sending empty request to queue
        for i in range(options.threads):
            queue.put(None)

        # wait for pending rendering jobs to complete
        queue.join()
        for i in range(options.threads):
            renderers[i].join()


    else:
        m = mapnik.Map(255,255)
        mapnik.load_map(m, style)
        
        for z in range(minzoom, maxzoom+1):
            n = 2**z
            for x in range(0, n):
                for y in range(0, n):
                    render_tile(m, z, x, y, scale, dir, type)

class RenderThread:
    def __init__(self, threadnum, queue, style, scale, dir, type, lock):
        self.threadnum = threadnum
        self.queue = queue
        self.scale = scale
        self.dir = dir
        self.type = type
        self.lock = lock
        self.style = style

    def run(self):
        m = mapnik.Map(255,255)
        mapnik.load_map(m, self.style, True)

        while True:
            r = self.queue.get()
            if (r == None):
                self.queue.task_done()
                self.lock.acquire()
                print "Thread #%u: closing" % (self.threadnum)
                self.lock.release()
                break
            else:
                (z, x, y) = r

            render_tile(m, z, x, y, self.scale, self.dir, self.type, self.lock, self.threadnum)
            self.queue.task_done()


def render_tile(m, z, x, y, scale, dir, type, lock=None, threadnum=None):
    n = 2**z
    n2 = n/2
    x2n = x-n2
    y2n = (n-y-1)-n2

    tilesize = scale / n;

    bbox = [
        tilesize * x2n,
        tilesize * y2n,
        tilesize * (x2n+1),
        tilesize * (y2n+1)
    ]
    pdir = dir + "/" + str(z) + "/" + str(x)

    if lock:
        lock.acquire()
        print "Thread #%u: z=%u x=%u y=%u -> n=%u, n2=%u -> (x2n=%u, y2n=%u) -> (%f,%f,%f,%f)" % (threadnum, z, x, y, n, n2, x2n, y2n, bbox[0], bbox[1], bbox[2], bbox[3])
        if not os.path.exists(pdir):
            os.makedirs(pdir)
        lock.release()
    else:
        print "Single-Thread: z=%u x=%u y=%u -> n=%u, n2=%u -> (x2n=%u, y2n=%u) -> (%f,%f,%f,%f)" % (z, x, y, n, n2, x2n, y2n, bbox[0], bbox[1], bbox[2], bbox[3])

    e = mapnik.Envelope(*bbox)
    
    # zoom map to bounding box
    m.zoom_to_box(e)
    
    file = dir + "/" + str(z) + "/" + str(x) + "/" + str(y) + "." + type
    s = mapnik.Image(255, 255)
    
    mapnik.render(m, s)
    
    view = s.view(0, 0, 255, 255)
    view.save(file, type)

if __name__ == "__main__":
  main()
