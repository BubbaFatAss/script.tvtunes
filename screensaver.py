# -*- coding: utf-8 -*-
import random
import sys
import os
import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui

if sys.version_info >= (2, 7):
    import json
else:
    import simplejson as json


__addon__ = xbmcaddon.Addon(id='script.tvtunes')
__cwd__ = __addon__.getAddonInfo('path').decode("utf-8")
__resource__ = xbmc.translatePath(os.path.join(__cwd__, 'resources').encode("utf-8")).decode("utf-8")
__lib__ = xbmc.translatePath(os.path.join(__resource__, 'lib').encode("utf-8")).decode("utf-8")
__media__ = xbmc.translatePath(os.path.join(__resource__, 'media').encode("utf-8")).decode("utf-8")

sys.path.append(__lib__)


from settings import ScreensaverSettings
from settings import log


class NoImagesException(Exception):
    pass


# Class used to create the correct type of screensaver class
class ScreensaverManager(object):
    # Creates the correct type of Screensaver class
    def __new__(cls):
        mode = ScreensaverSettings.getMode()
        if mode == 'Random':
            # Just choose one of the options at random from everything that
            # extends the base screensaver
            subcls = random.choice(ScreensaverBase.__subclasses__())
            return subcls()
        # Find out which screensaver format is selected
        for subcls in ScreensaverBase.__subclasses__():
            if subcls.MODE == mode:
                return subcls()
        raise ValueError('Not a valid ScreensaverBase subclass: %s' % mode)


# Monitor class to handle events like the screensaver deactivating
class ExitMonitor(xbmc.Monitor):
    # Create the monitor passing in the method to call when we want to exit
    # and stop the screensaver
    def __init__(self, exit_callback):
        self.exit_callback = exit_callback

    # Called when the screensaver should be stopped
    def onScreensaverDeactivated(self):
        # Make the callback to stop the screensaver
        self.exit_callback()


# The Dialog used to display the screensaver in
class ScreensaverWindow(xbmcgui.WindowDialog):
    # Create the Dialog, giving the method to call when it is exited
    def __init__(self, exit_callback):
        self.exit_callback = exit_callback

    # Handle the action to exit the screensaver
    def onAction(self, action):
        action_id = action.getId()
        if action_id in [9, 10, 13, 92]:
            self.exit_callback()


# Class to hold all of the media files used that are stored in the addon
class MediaFiles(object):
    LOADING_IMAGE = os.path.join(__media__, 'loading.gif')
    BLACK_IMAGE = os.path.join(__media__, 'black.jpg')
    STARS_IMAGE = os.path.join(__media__, 'stars.jpg')
    TABLE_IMAGE = os.path.join(__media__, 'table.jpg')


# Base Screensaver class that handles all of the operations for a screensaver
class ScreensaverBase(object):
    MODE = None
    IMAGE_CONTROL_COUNT = 10
    FAST_IMAGE_COUNT = 0
    NEXT_IMAGE_TIME = 2000
    BACKGROUND_IMAGE = MediaFiles.BLACK_IMAGE

    def __init__(self):
        log('Screensaver: __init__ start')
        self.exit_requested = False
        self.background_control = None
        self.preload_control = None
        self.image_count = 0
        self.image_controls = []
        self.global_controls = []
        self.exit_monitor = ExitMonitor(self.stop)
        self.xbmc_window = ScreensaverWindow(self.stop)
        self.xbmc_window.show()
        self.init_global_controls()
        self.load_settings()
        self.init_cycle_controls()
        self.stack_cycle_controls()
        log('Screensaver: __init__ end')

    def init_global_controls(self):
        log('Screensaver: init_global_controls start')
        self.loading_control = xbmcgui.ControlImage(576, 296, 128, 128, MediaFiles.LOADING_IMAGE)
        self.preload_control = xbmcgui.ControlImage(-1, -1, 1, 1, '')
        self.background_control = xbmcgui.ControlImage(0, 0, 1280, 720, '')
        self.global_controls = [self.preload_control, self.background_control, self.loading_control]
        self.xbmc_window.addControls(self.global_controls)
        log('Screensaver: init_global_controls end')

    def load_settings(self):
        pass

    def init_cycle_controls(self):
        log('Screensaver: init_cycle_controls start')
        for i in xrange(self.IMAGE_CONTROL_COUNT):
            img_control = xbmcgui.ControlImage(0, 0, 0, 0, '', aspectRatio=1)
            self.image_controls.append(img_control)
        log('Screensaver: init_cycle_controls end')

    def stack_cycle_controls(self):
        log('Screensaver: stack_cycle_controls start')
        # add controls to the window in same order as image_controls list
        # so any new image will be in front of all previous images
        self.xbmc_window.addControls(self.image_controls)
        log('Screensaver: stack_cycle_controls end')

    def start_loop(self):
        log('Screensaver: start_loop start')
        images = self.get_images()
        if ScreensaverSettings.getRandomOrder():
            random.shuffle(images)
        image_url_cycle = self._cycle(images)
        image_controls_cycle = self._cycle(self.image_controls)
        self.hide_loading_indicator()
        image_url = image_url_cycle.next()
        while not self.exit_requested:
            log('Screensaver: using image: %s' % repr(image_url))
            image_control = image_controls_cycle.next()
            self.process_image(image_control, image_url)
            image_url = image_url_cycle.next()
            if self.image_count < self.FAST_IMAGE_COUNT:
                self.image_count += 1
            else:
                self.preload_image(image_url)
                self.wait()
        log('Screensaver: start_loop end')

    def _cycle(self, iterable):
        saved = []
        for element in iterable:
            yield element
            saved.append(element)
        while saved:
            for element in saved:
                yield element

    def get_images(self):
        log('Screensaver: get_images')
        self.image_aspect_ratio = 16.0 / 9.0
        source = ScreensaverSettings.getSource()
        prop = ScreensaverSettings.getProps()
        images = []
        if source == 'movies':
            images = self._getJsonImages('VideoLibrary.GetMovies', 'movies', prop)
        elif source == 'tvshows':
            images = self._getJsonImages('VideoLibrary.GetTVShows', 'tvshows', prop)
        elif source == 'image_folder':
            path = ScreensaverSettings.getImagePath()
            if path:
                images = self._getFolderImages(path)
        if not images:
            cmd = 'XBMC.Notification("{0}", "{1}")'.format(__addon__.getLocalizedString(32995), __addon__.getLocalizedString(32996))
            xbmc.executebuiltin(cmd)
            images = (self._getJsonImages('VideoLibrary.GetMovies', 'movies', 'fanart'))
        if not images:
            raise NoImagesException
        return images

    def _getJsonImages(self, method, key, prop):
        log("Screensaver: getJsonImages for %s" % key)
        query = {'jsonrpc': '2.0', 'id': 0, 'method': method, 'params': {'properties': [prop], }}
        response = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        images = [element[prop] for element
                  in response.get('result', {}).get(key, [])
                  if element.get(prop)]
        log("Screensaver: Found %d images for %s" % (len(images), key))
        return images

    def _getFolderImages(self, path):
        log('Screensaver: getFolderImages for path: %s' % repr(path))
        dirs, files = xbmcvfs.listdir(path)
        images = [xbmc.validatePath(path + f) for f in files
                  if f.lower()[-3:] in ('jpg', 'png')]
        if ScreensaverSettings.getRecursive():
            for directory in dirs:
                if directory.startswith('.'):
                    continue
                images.extend(self._getFolderImages(xbmc.validatePath('/'.join((path, directory, '')))))
        log("Screensaver: Found %d images for %s" % (len(images), path))
        return images

    def hide_loading_indicator(self):
        self.loading_control.setAnimations([('conditional', 'effect=fade start=100 end=0 time=500 condition=true')])
        self.background_control.setAnimations([('conditional', 'effect=fade start=0 end=100 time=500 delay=500 condition=true')])
        self.background_control.setImage(self.BACKGROUND_IMAGE)

    def process_image(self, image_control, image_url):
        # Needs to be implemented in sub class
        raise NotImplementedError

    def preload_image(self, image_url):
        # set the next image to an invisible image-control for caching
        log('Screensaver: preloading image: %s' % repr(image_url))
        self.preload_control.setImage(image_url)
        log('Screensaver: preloading done')

    def wait(self):
        CHUNK_WAIT_TIME = 250
        # wait in chunks of 500ms to react earlier on exit request
        chunk_wait_time = int(CHUNK_WAIT_TIME)
        remaining_wait_time = int(self.NEXT_IMAGE_TIME)
        while remaining_wait_time > 0:
            if self.exit_requested:
                log('Screensaver: wait aborted')
                return
            if remaining_wait_time < chunk_wait_time:
                chunk_wait_time = remaining_wait_time
            remaining_wait_time -= chunk_wait_time
            xbmc.sleep(chunk_wait_time)

    def stop(self):
        log('Screensaver: stop')
        self.exit_requested = True
        self.exit_monitor = None

    def close(self):
        self.del_controls()

    def del_controls(self):
        log('Screensaver: del_controls start')
        self.xbmc_window.removeControls(self.image_controls)
        self.xbmc_window.removeControls(self.global_controls)
        self.preload_control = None
        self.background_control = None
        self.loading_control = None
        self.image_controls = []
        self.global_controls = []
        self.xbmc_window.close()
        self.xbmc_window = None
        log('Screensaver: del_controls end')


class TableDropScreensaver(ScreensaverBase):
    MODE = 'TableDrop'
    BACKGROUND_IMAGE = MediaFiles.TABLE_IMAGE
    IMAGE_CONTROL_COUNT = 20
    FAST_IMAGE_COUNT = 0
    NEXT_IMAGE_TIME = 1500
    MIN_WIDTH = 500
    MAX_WIDTH = 700

    def load_settings(self):
        self.NEXT_IMAGE_TIME = ScreensaverSettings.getTableDropWait()

    def process_image(self, image_control, image_url):
        ROTATE_ANIMATION = ('effect=rotate start=0 end=%d center=auto time=%d delay=0 tween=circle condition=true')
        DROP_ANIMATION = ('effect=zoom start=%d end=100 center=auto time=%d delay=0 tween=circle condition=true')
        FADE_ANIMATION = ('effect=fade start=0 end=100 time=200 condition=true')
        # hide the image
        image_control.setVisible(False)
        image_control.setImage('')
        # re-stack it (to be on top)
        self.xbmc_window.removeControl(image_control)
        self.xbmc_window.addControl(image_control)
        # calculate all parameters and properties
        width = random.randint(self.MIN_WIDTH, self.MAX_WIDTH)
        height = int(width / self.image_aspect_ratio)
        x_position = random.randint(0, 1280 - width)
        y_position = random.randint(0, 720 - height)
        drop_height = random.randint(400, 800)
        drop_duration = drop_height * 1.5
        rotation_degrees = random.uniform(-20, 20)
        rotation_duration = drop_duration
        animations = [('conditional', FADE_ANIMATION),
                      ('conditional', ROTATE_ANIMATION % (rotation_degrees, rotation_duration)),
                      ('conditional', DROP_ANIMATION % (drop_height, drop_duration))]
        # set all parameters and properties
        image_control.setImage(image_url)
        image_control.setPosition(x_position, y_position)
        image_control.setWidth(width)
        image_control.setHeight(height)
        image_control.setAnimations(animations)
        # show the image
        image_control.setVisible(True)


class StarWarsScreensaver(ScreensaverBase):
    MODE = 'StarWars'
    BACKGROUND_IMAGE = MediaFiles.STARS_IMAGE
    IMAGE_CONTROL_COUNT = 6
    SPEED = 0.5

    def load_settings(self):
        self.SPEED = ScreensaverSettings.getStarwarsSpeed()
        self.EFFECT_TIME = 9000.0 / self.SPEED
        self.NEXT_IMAGE_TIME = self.EFFECT_TIME / 7.6

    def process_image(self, image_control, image_url):
        TILT_ANIMATION = ('effect=rotatex start=0 end=55 center=auto time=0 condition=true')
        MOVE_ANIMATION = ('effect=slide start=0,1280 end=0,-2560 time=%d tween=linear condition=true')
        # hide the image
        image_control.setImage('')
        image_control.setVisible(False)
        # re-stack it (to be on top)
        self.xbmc_window.removeControl(image_control)
        self.xbmc_window.addControl(image_control)
        # calculate all parameters and properties
        width = 1280
        height = 720
        x_position = 0
        y_position = 0
        animations = [('conditional', TILT_ANIMATION),
                      ('conditional', MOVE_ANIMATION % self.EFFECT_TIME)]
        # set all parameters and properties
        image_control.setPosition(x_position, y_position)
        image_control.setWidth(width)
        image_control.setHeight(height)
        image_control.setAnimations(animations)
        image_control.setImage(image_url)
        # show the image
        image_control.setVisible(True)


class RandomZoomInScreensaver(ScreensaverBase):
    MODE = 'RandomZoomIn'
    IMAGE_CONTROL_COUNT = 7
    NEXT_IMAGE_TIME = 2000
    EFFECT_TIME = 5000

    def load_settings(self):
        self.NEXT_IMAGE_TIME = ScreensaverSettings.getRandonZoomWait()
        self.EFFECT_TIME = ScreensaverSettings.getRandonZoomEffect()

    def process_image(self, image_control, image_url):
        ZOOM_ANIMATION = ('effect=zoom start=1 end=100 center=%d,%d time=%d tween=quadratic condition=true')
        # hide the image
        image_control.setVisible(False)
        image_control.setImage('')
        # re-stack it (to be on top)
        self.xbmc_window.removeControl(image_control)
        self.xbmc_window.addControl(image_control)
        # calculate all parameters and properties
        width = 1280
        height = 720
        x_position = 0
        y_position = 0
        zoom_x = random.randint(0, 1280)
        zoom_y = random.randint(0, 720)
        animations = [('conditional', ZOOM_ANIMATION % (zoom_x, zoom_y, self.EFFECT_TIME))]
        # set all parameters and properties
        image_control.setImage(image_url)
        image_control.setPosition(x_position, y_position)
        image_control.setWidth(width)
        image_control.setHeight(height)
        image_control.setAnimations(animations)
        # show the image
        image_control.setVisible(True)


class AppleTVLikeScreensaver(ScreensaverBase):
    MODE = 'AppleTVLike'
    IMAGE_CONTROL_COUNT = 35
    FAST_IMAGE_COUNT = 2
    DISTANCE_RATIO = 0.7
    SPEED = 1.0
    CONCURRENCY = 1.0

    def load_settings(self):
        self.SPEED = ScreensaverSettings.getAppletvlikeSpeed()
        self.CONCURRENCY = ScreensaverSettings.getAppletvlikeConcurrency()
        self.MAX_TIME = int(15000 / self.SPEED)
        self.NEXT_IMAGE_TIME = int(4500.0 / self.CONCURRENCY / self.SPEED)

    def stack_cycle_controls(self):
        # randomly generate a zoom in percent as betavariant
        # between 10 and 70 and assign calculated width to control.
        # Remove all controls from window and re-add sorted by size.
        # This is needed because the bigger (=nearer) ones need to be in front
        # of the smaller ones.
        # Then shuffle image list again to have random size order.

        for image_control in self.image_controls:
            zoom = int(random.betavariate(2, 2) * 40) + 10
            # zoom = int(random.randint(10, 70))
            width = 1280 / 100 * zoom
            image_control.setWidth(width)
        self.image_controls = sorted(self.image_controls, key=lambda c: c.getWidth())
        self.xbmc_window.addControls(self.image_controls)
        random.shuffle(self.image_controls)

    def process_image(self, image_control, image_url):
        MOVE_ANIMATION = ('effect=slide start=0,720 end=0,-720 center=auto time=%s tween=linear delay=0 condition=true')
        image_control.setVisible(False)
        image_control.setImage('')
        # calculate all parameters and properties based on the already set
        # width. We can not change the size again because all controls need
        # to be added to the window in size order.
        width = image_control.getWidth()
        zoom = width * 100 / 1280
        height = int(width / self.image_aspect_ratio)
        # let images overlap max 1/2w left or right
        center = random.randint(0, 1280)
        x_position = center - width / 2
        y_position = 0

        time = self.MAX_TIME / zoom * self.DISTANCE_RATIO * 100

        animations = [('conditional', MOVE_ANIMATION % time)]
        # set all parameters and properties
        image_control.setImage(image_url)
        image_control.setPosition(x_position, y_position)
        image_control.setWidth(width)
        image_control.setHeight(height)
        image_control.setAnimations(animations)
        # show the image
        image_control.setVisible(True)


class GridSwitchScreensaver(ScreensaverBase):
    MODE = 'GridSwitch'
    ROWS_AND_COLUMNS = 4
    NEXT_IMAGE_TIME = 1000
    EFFECT_TIME = 500
    RANDOM_ORDER = False

    IMAGE_CONTROL_COUNT = ROWS_AND_COLUMNS ** 2
    FAST_IMAGE_COUNT = IMAGE_CONTROL_COUNT

    def load_settings(self):
        self.NEXT_IMAGE_TIME = ScreensaverSettings.getGridswitchWait()
        self.ROWS_AND_COLUMNS = ScreensaverSettings.getGridswitchRowsColumns()
        self.RANDOM_ORDER = ScreensaverSettings.getGridswitchRandom()
        self.IMAGE_CONTROL_COUNT = self.ROWS_AND_COLUMNS ** 2
        self.FAST_IMAGE_COUNT = self.IMAGE_CONTROL_COUNT

    def stack_cycle_controls(self):
        # Set position and dimensions based on stack position.
        # Shuffle image list to have random order.
        super(GridSwitchScreensaver, self).stack_cycle_controls()
        for i, image_control in enumerate(self.image_controls):
            current_row, current_col = divmod(i, self.ROWS_AND_COLUMNS)
            width = 1280 / self.ROWS_AND_COLUMNS
            height = 720 / self.ROWS_AND_COLUMNS
            x_position = width * current_col
            y_position = height * current_row
            image_control.setPosition(x_position, y_position)
            image_control.setWidth(width)
            image_control.setHeight(height)
        if self.RANDOM_ORDER:
            random.shuffle(self.image_controls)

    def process_image(self, image_control, image_url):
        if not self.image_count < self.FAST_IMAGE_COUNT:
            FADE_OUT_ANIMATION = ('effect=fade start=100 end=0 time=%d condition=true' % self.EFFECT_TIME)
            animations = [('conditional', FADE_OUT_ANIMATION)]
            image_control.setAnimations(animations)
            xbmc.sleep(self.EFFECT_TIME)
        image_control.setImage(image_url)
        FADE_IN_ANIMATION = ('effect=fade start=0 end=100 time=%d condition=true' % self.EFFECT_TIME)
        animations = [('conditional', FADE_IN_ANIMATION)]
        image_control.setAnimations(animations)


if __name__ == '__main__':
    screensaver = ScreensaverManager()
    try:
        screensaver.start_loop()
    except NoImagesException:
        pass
    screensaver.close()
    del screensaver
    sys.modules.clear()
