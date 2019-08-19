import numpy
import os
import pickle
import PIL.Image, PIL.ImageDraw
from colors.nn import predict, PARAMS_PICKLED
from colors.conversion import rgb2lab, cie94, ciede2000


class RGB:
    def embed(self, colors):
        return colors

    def dist(self, p, q):
        return numpy.sum((p - q)**2, axis=1)


class Lab:
    def embed(self, colors):
        return rgb2lab(colors)

    def dist(self, p, q):
        return numpy.sum((p - q)**2, axis=1)


class CIE94:
    def embed(self, colors):
        return rgb2lab(colors)

    def dist(self, p, q):
        return cie94(p, q)


class CIEDE2000:
    def embed(self, colors):
        return rgb2lab(colors)

    def dist(self, p, q):
        return ciede2000(p, q)


class NN:
    def __init__(self):
        with open(PARAMS_PICKLED, 'rb') as f:
            self.params = pickle.load(f)

    def embed(self, colors):
        embedded = predict(self.params, colors, dropout=False)
        return embedded / numpy.sum(embedded**2, axis=1)[:,numpy.newaxis]**0.5

    def dist(self, p, q):
        return numpy.sum((p - q)**2, axis=1)


class Cycler:
    def __init__(self, method=NN, remove_bw=True, seed=None, eps=1e-9):
        # Build matrix of 16x16x16 colors
        vs = list(range(0, 256, 17))
        all_rgb = []
        for r in vs:
            for g in vs:
                for b in vs:
                    all_rgb.append((r/255, g/255, b/255))
        self.all_rgb = numpy.array(all_rgb)
        self.m = method()
        self.all_rgb_embedded = self.m.embed(self.all_rgb)
        if seed is None:
            seed = numpy.eye(3)
        else:
            seed = numpy.array(seed)
        if remove_bw:
            seed = numpy.vstack([numpy.array([(0, 0, 0), (1, 1, 1)]), seed])
        self.seed = seed
        self.seed_embedded = self.m.embed(seed)
        self.colors = []
        self.min_dist = numpy.array([float('inf')]*len(self.all_rgb))
        self.eps = eps
        self.remove_bw = remove_bw

    def __iter__(self):
        def gen():
            i = 0
            while True:
                yield self[i]
                i += 1
        return gen()

    def __getitem__(self, key):
        if isinstance(key, slice):
            return [self[i] for i in range(*key.indices(2**99))]
        assert isinstance(key, int)
        if self.remove_bw:
            key += 2
        while len(self.colors) <= key:
            if key < len(self.seed_embedded):
                # Just use the seed
                j = len(self.colors)
                color = self.seed[j]
                last_vector_embedded = self.seed_embedded[j]
            else:
                # Find the next color
                j = numpy.argmax(self.min_dist)
                color = self.all_rgb[j]
                last_vector_embedded = self.all_rgb_embedded[j]

            # Update min dist for this color
            last_vector_embedded = last_vector_embedded[numpy.newaxis,:]
            self.min_dist = numpy.minimum(self.min_dist, self.m.dist(last_vector_embedded, self.all_rgb_embedded))
            self.min_dist += self.eps
            self.colors.append(color)

        return self.colors[key]


if __name__ == '__main__':
    for fn, obj in [
            ('rgb.png', RGB),
            ('lab.png', Lab),
            ('cie94.png', CIE94),
            ('ciede2000.png', CIEDE2000),
            ('nn.png', NN)
            ]:
        cycler = Cycler(method=obj)
        colors = cycler[:2**8]

        # Generate Matplotlib colormap format
        # print([list(c) + [1] for c in colors])

        d, e = 40, 10
        k = int(numpy.ceil(len(colors)**0.5/2))*2
        colors = numpy.reshape(colors, (k, k, 3))
        im = PIL.Image.new('RGB', (2*k*d+3*e, k*d+2*e))
        draw = PIL.ImageDraw.Draw(im)

        def draw_patches(colors, x_offset, y_offset):
            for row in range(colors.shape[0]):
                for col in range(colors.shape[1]):
                    draw.rectangle((col*d+x_offset, row*d+y_offset, (col+1)*d+x_offset, (row+1)*d+y_offset), fill=tuple(int(255*z) for z in colors[row][col]))

        draw_patches(colors, e, e)
        colors = numpy.array(sorted(numpy.reshape(colors, (k*k, 3)), key=lambda c: sum(c)))
        colors = numpy.reshape(colors, (2, 2, k//2, k//2, 3))
        for i in range(2):
            for j in range(2):
                rect = colors[i,j]
                for _ in range(100):
                    for row in range(rect.shape[1]):
                        rect[row,:] = numpy.array(sorted(rect[row,:], key=lambda c: c[1] - c[0]))
                    for col in range(rect.shape[2]):
                        rect[:,col] = numpy.array(sorted(rect[:,col], key=lambda c: c[2] - c[1]))
                draw_patches(rect, k*d+2*e + i*k/2*d, e + j*k/2*d)

        DIR = 'pics'
        if not os.path.exists(DIR):
            os.makedirs(DIR)
        im.save(os.path.join(DIR, fn))