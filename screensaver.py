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
from themeFinder import ThemeFiles


# Helper method to allow the cycling through a list of values
def _cycle(iterable):
    saved = []
    for element in iterable:
        yield element
        saved.append(element)
    while saved:
        for element in saved:
            yield element


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


# Class to hold groups of images and media
class MediaGroup(object):
    def __init__(self, videoPath="", imageArray=[]):
        self.isPlayingTheme = False
        # Check if the user wants to play themes
        if ScreensaverSettings.isPlayThemes():
            self.themeFiles = ThemeFiles(videoPath)
        else:
            # If the user does not want to play themes, just have an empty set of themes
            self.themeFiles = ThemeFiles("")
        self.images = []
        # If images were supplied, then add them to the list
        for img in imageArray:
            self.addImage(img, 16.0 / 9.0)
        self.imageDetails_cycle = None
        self.firstImage = None
        self.imageRepeat = False

    # Add an image to the group, giving it's aspect radio
    def addImage(self, imageURL, aspectRatio):
        imageDetails = {'file': imageURL, 'aspect_ratio': aspectRatio}
        self.images.append(imageDetails)

    # get all the images in the group
    def getImageDetails(self):
        # Before returning the images, make sure they are all random
        random.shuffle(self.images)
        return self.images

    # Gets the number of images in the group
    def imageCount(self):
        return len(self.images)

    def hasLooped(self):
        return self.imageRepeat

    # Start playing a theme if there is one to play
    def startTheme(self):
        if self.themeFiles.hasThemes() and not xbmc.Player().isPlayingAudio():
            # Don't start the theme if we have already  shown all the images
            if not self.imageRepeat:
                self.isPlayingTheme = True
                xbmc.Player().play(self.themeFiles.getThemePlaylist())

    # Check if the theme has completed playing
    def completedGroup(self):
        if self.themeFiles.hasThemes() and xbmc.Player().isPlayingAudio():
            return False
        self.isPlayingTheme = False
        return True

    # Stop the theme playing if it is currently playing
    # NOTE: If you stop a theme that is playing, then it will also
    # exit out of the screensaver
    def stopTheme(self):
        if self.isPlayingTheme:
            self.isPlayingTheme = False
            if xbmc.Player().isPlayingAudio():
                xbmc.Player().stop()

    # Gets the next image details
    def getNextImage(self):
        if self.imageDetails_cycle is None:
            # Before using the images, make sure they are all random
            random.shuffle(self.images)
            # Create the handle for the cycle
            self.imageDetails_cycle = _cycle(self.images)
        # Get the next image details
        imageDetails = self.imageDetails_cycle.next()
        # Check to see if we have stored details of the first image processed
        # This was we know where the list started and ends
        if self.firstImage is None:
            self.firstImage = imageDetails['file']
        else:
            # Check if we have looped through all the images
            if imageDetails['file'] == self.firstImage:
                self.imageRepeat = True

        return imageDetails


# Base Screensaver class that handles all of the operations for a screensaver
class ScreensaverBase(object):
    MODE = None
    IMAGE_CONTROL_COUNT = 10
    FAST_IMAGE_COUNT = 0
    BACKGROUND_IMAGE = MediaFiles.BLACK_IMAGE

    def __init__(self):
        log('Screensaver: __init__ start')
        self.exit_requested = False

        # Set up all the required controls for the window
        self.loading_control = xbmcgui.ControlImage(576, 296, 128, 128, MediaFiles.LOADING_IMAGE)
        self.background_control = xbmcgui.ControlImage(0, 0, 1280, 720, '')
        self.preload_control = xbmcgui.ControlImage(-1, -1, 1, 1, '')
        self.global_controls = [self.preload_control, self.background_control, self.loading_control]

        self.image_count = 0
        self.image_controls = []
        self.exit_monitor = ExitMonitor(self.stop)
        self.xbmc_window = ScreensaverWindow(self.stop)
        self.xbmc_window.show()

        # Add all the controls to the window
        self.xbmc_window.addControls(self.global_controls)

        self.load_settings()
        self.init_cycle_controls()
        self.stack_cycle_controls()
        log('Screensaver: __init__ end')

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
        imageGroups = self.getImageGroups()
        # We have a lot of groups (Each different Movie or TV Show) so
        # mix them all up so they are not always in the same order
        random.shuffle(imageGroups)

        imageGroup_cycle = _cycle(imageGroups)
        image_controls_cycle = _cycle(self.image_controls)
        self.hide_loading_indicator()
        imageGroup = imageGroup_cycle.next()
        imageDetails = imageGroup.getNextImage()

        while not self.exit_requested:
            log('Screensaver: using image: %s' % repr(imageDetails['file']))

            # Start playing theme if there is one
            imageGroup.startTheme()
            # Get the next control and set it displaying the image
            image_control = image_controls_cycle.next()
            self.process_image(image_control, imageDetails)
            # Now that we are showing the last image, load up the next one
            imageDetails = imageGroup.getNextImage()

            # At this point we have moved the image onto the next one
            # so check if we have gone in a complete loop and there is
            # another group of images to pre-load

            # Wait for the theme to complete playing at least once, if it has not
            # completed playing the theme at least once, then we can safely repeat
            # the images we show
            if imageGroup.hasLooped() and (len(imageGroups) > 1) and imageGroup.completedGroup():
                # Move onto the next group, and the first image in that group
                imageGroup = imageGroup_cycle.next()
                # Get the next image from the new group
                imageDetails = imageGroup.getNextImage()

            if self.image_count < self.FAST_IMAGE_COUNT:
                self.image_count += 1
            else:
                # Pre-load the next image that is going to be shown
                self.preload_image(imageDetails['file'])
                # Wait before showing the next image
                self.wait()

        # Make sure we stop any outstanding playing theme
        imageGroup.stopTheme()

        log('Screensaver: start_loop end')

    # Gets the set of images that are going to be used
    def getImageGroups(self):
        log('Screensaver: getImageGroups')
        source = ScreensaverSettings.getSource()
        imageTypes = ScreensaverSettings.getImageTypes()

        imageGroups = []
        if 'movies' in source:
            imgGrp = self._getJsonImageGroups('VideoLibrary.GetMovies', 'movies', imageTypes)
            imageGroups.extend(imgGrp)
        if 'tvshows' in source:
            imgGrp = self._getJsonImageGroups('VideoLibrary.GetTVShows', 'tvshows', imageTypes)
            imageGroups.extend(imgGrp)
        if 'image_folder' in source:
            path = ScreensaverSettings.getImagePath()
            if path:
                imgGrp = self._getFolderImages(path)
                imageGroups.extend(imgGrp)
        if not imageGroups:
            cmd = 'XBMC.Notification("{0}", "{1}")'.format(__addon__.getLocalizedString(32101), __addon__.getLocalizedString(32995))
            xbmc.executebuiltin(cmd)
            raise NoImagesException
        return imageGroups

    # Makes a JSON call to get the images for a given category
    def _getJsonImageGroups(self, method, key, imageTypes):
        log("Screensaver: getJsonImages for %s" % key)
        jsonProps = list(imageTypes)
        # The file is actually the path for a TV Show, the video file for movies
        jsonProps.append('file')
        query = {'jsonrpc': '2.0', 'id': 0, 'method': method, 'params': {'properties': jsonProps}}
        response = json.loads(xbmc.executeJSONRPC(json.dumps(query)))

        mediaGroups = []
        if ('result' in response) and (key in response['result']):
            for item in response['result'][key]:
                # Check to see if we can get the path or file for the video
                if 'file' in item:
                    mediaGroup = MediaGroup(item['file'])
                    # Now get all the image information
                    for prop in imageTypes:
                        if prop in item:
                            # If we are dealing with fanart or thumbnail, then we can just store this value
                            if prop in ['fanart']:
                                # Set the aspect radio based on the type of image being shown
                                mediaGroup.addImage(item[prop], 16.0 / 9.0)
                            elif prop in ['thumbnail']:
                                mediaGroup.addImage(item[prop], 2.0 / 3.0)
                            elif prop in ['cast']:
                                # If this cast member has an image, add it to the array
                                for castItem in item['cast']:
                                    if 'thumbnail' in castItem:
                                        mediaGroup.addImage(castItem['thumbnail'], 2.0 / 3.0)
                    # Don't return an empty image list if there are no images
                    if mediaGroup.imageCount > 0:
                        mediaGroups.append(mediaGroup)
                else:
                    log("Screensaver: No file specified when searching")
        log("Screensaver: Found %d image sets for %s" % (len(mediaGroups), key))
        return mediaGroups

    # Creates a group containing all the images in a given directory
    def _getFolderImages(self, path):
        log('Screensaver: getFolderImages for path: %s' % repr(path))
        dirs, files = xbmcvfs.listdir(path)
        images = [xbmc.validatePath(path + f) for f in files
                  if f.lower()[-3:] in ('jpg', 'png')]
        if ScreensaverSettings.isRecursive():
            for directory in dirs:
                if directory.startswith('.'):
                    continue
                images.extend(self._getFolderImages(xbmc.validatePath('/'.join((path, directory, '')))))
        log("Screensaver: Found %d images for %s" % (len(images), path))
        mediaGroup = MediaGroup(imageArray=images)
        return [mediaGroup]

    def hide_loading_indicator(self):
        self.loading_control.setAnimations([('conditional', 'effect=fade start=100 end=0 time=500 condition=true')])
        self.background_control.setAnimations([('conditional', 'effect=fade start=0 end=100 time=500 delay=500 condition=true')])
        self.background_control.setImage(self.BACKGROUND_IMAGE)

    def process_image(self, image_control, imageDetails):
        # Needs to be implemented in sub class
        raise NotImplementedError

    def preload_image(self, image_url):
        # set the next image to an invisible image-control for caching
        log('Screensaver: preloading image: %s' % repr(image_url))
        self.preload_control.setImage(image_url)
        log('Screensaver: preloading done')

    # Wait for the image to finish being displayed before starting on the next one
    def wait(self):
        CHUNK_WAIT_TIME = 250
        # wait in chunks of 500ms to react earlier on exit request
        chunk_wait_time = int(CHUNK_WAIT_TIME)
        remaining_wait_time = self.getNextImageTime()
        while remaining_wait_time > 0:
            if self.exit_requested:
                log('Screensaver: wait aborted')
                return
            if remaining_wait_time < chunk_wait_time:
                chunk_wait_time = remaining_wait_time
            remaining_wait_time -= chunk_wait_time
            xbmc.sleep(chunk_wait_time)

    # Get how long to wait until the next image is shown
    def getNextImageTime(self):
        # Needs to be implemented in sub class
        raise NotImplementedError

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
    MIN_WIDEST_DIMENSION = 500
    MAX_WIDEST_DIMENSION = 700

    def load_settings(self):
        self.NEXT_IMAGE_TIME = ScreensaverSettings.getWaitTime()

    # Get how long to wait until the next image is shown
    def getNextImageTime(self):
        # There is an even amount of time between each image drop
        return int(self.NEXT_IMAGE_TIME)

    def process_image(self, image_control, imageDetails):
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
        # check if wider or taller, then set the dimensions from that
        if imageDetails['aspect_ratio'] < 1.0:
            height = random.randint(self.MIN_WIDEST_DIMENSION, self.MAX_WIDEST_DIMENSION)
            width = int(height * imageDetails['aspect_ratio'])
        else:
            width = random.randint(self.MIN_WIDEST_DIMENSION, self.MAX_WIDEST_DIMENSION)
            height = int(width / imageDetails['aspect_ratio'])
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
        image_control.setImage(imageDetails['file'])
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
        self.SPEED = ScreensaverSettings.getSpeed()
        self.EFFECT_TIME = 9000.0 / self.SPEED
        self.NEXT_IMAGE_TIME = self.EFFECT_TIME / 11

        # If we are dealing with a fanart image, then it will be
        # targeted at 1280 x 720, this would calculate as follows:
        # int(self.EFFECT_TIME / 11)
        # if the item is a thumbnail, then the proportions are different
        # in fact is will be 1280 x 1920 so we need to wait 2.8 times as along
        for imgType in ScreensaverSettings.getImageTypes():
            if imgType in ['thumbnail', 'cast']:
                self.NEXT_IMAGE_TIME = self.NEXT_IMAGE_TIME * 2.7
                break

    # Get how long to wait until the next image is shown
    def getNextImageTime(self):
        return int(self.NEXT_IMAGE_TIME)

    def process_image(self, image_control, imageDetails):
        TILT_ANIMATION = ('effect=rotatex start=0 end=55 center=auto time=0 condition=true')
        MOVE_ANIMATION = ('effect=slide start=0,2000 end=0,-3840 time=%d tween=linear condition=true')
        # hide the image
        image_control.setImage('')
        image_control.setVisible(False)
        # re-stack it (to be on top)
        self.xbmc_window.removeControl(image_control)
        self.xbmc_window.addControl(image_control)
        # calculate all parameters and properties
        width = 1280
        height = int(width / imageDetails['aspect_ratio'])
        x_position = 0
        y_position = 0
        if height > 720:
            y_position = int((height - 720) / -2)
        animations = [('conditional', TILT_ANIMATION),
                      ('conditional', MOVE_ANIMATION % self.EFFECT_TIME)]
        # set all parameters and properties
        image_control.setPosition(x_position, y_position)
        image_control.setWidth(width)
        image_control.setHeight(height)
        image_control.setAnimations(animations)
        image_control.setImage(imageDetails['file'])
        # show the image
        image_control.setVisible(True)


class RandomZoomInScreensaver(ScreensaverBase):
    MODE = 'RandomZoomIn'
    IMAGE_CONTROL_COUNT = 7
    NEXT_IMAGE_TIME = 2000
    EFFECT_TIME = 5000

    def load_settings(self):
        self.NEXT_IMAGE_TIME = ScreensaverSettings.getWaitTime()
        self.EFFECT_TIME = ScreensaverSettings.getEffectTime()

    # Get how long to wait until the next image is shown
    def getNextImageTime(self):
        # Even amount of time between each zoom
        return int(self.NEXT_IMAGE_TIME)

    def process_image(self, image_control, imageDetails):
        ZOOM_ANIMATION = ('effect=zoom start=1 end=100 center=%d,%d time=%d tween=quadratic condition=true')
        # hide the image
        image_control.setVisible(False)
        image_control.setImage('')
        # re-stack it (to be on top)
        self.xbmc_window.removeControl(image_control)
        self.xbmc_window.addControl(image_control)
        # calculate all parameters and properties
        width = 1280
        height = int(width / imageDetails['aspect_ratio'])
        x_position = 0
        y_position = 0
        # Make sure if the image is too large to all fit on the screen
        # then make sure it is zoomed into about a third down, this is because
        # it is most probably a DVD Cover of Cast member, so it will result in
        # the focus at a better location after the zoom
        if height > 720:
            y_position = int((height - 720) / -3)
        zoom_x = random.randint(0, 1280)
        zoom_y = random.randint(0, 720)
        animations = [('conditional', ZOOM_ANIMATION % (zoom_x, zoom_y, self.EFFECT_TIME))]
        # set all parameters and properties
        image_control.setImage(imageDetails['file'])
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
        self.SPEED = ScreensaverSettings.getSpeed()
        self.CONCURRENCY = ScreensaverSettings.getAppletvlikeConcurrency()
        self.MAX_TIME = int(15000 / self.SPEED)
        self.NEXT_IMAGE_TIME = int(4500.0 / self.CONCURRENCY / self.SPEED)

    # Get how long to wait until the next image is shown
    def getNextImageTime(self):
        return int(self.NEXT_IMAGE_TIME)

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

    def process_image(self, image_control, imageDetails):
        MOVE_ANIMATION = ('effect=slide start=0,720 end=0,-720 center=auto time=%s tween=linear delay=0 condition=true')
        image_control.setVisible(False)
        image_control.setImage('')
        # calculate all parameters and properties based on the already set
        # width. We can not change the size again because all controls need
        # to be added to the window in size order.
        width = image_control.getWidth()
        zoom = width * 100 / 1280
        height = int(width / imageDetails['aspect_ratio'])
        # let images overlap max 1/2w left or right
        center = random.randint(0, 1280)
        x_position = center - width / 2
        y_position = 0

        time = self.MAX_TIME / zoom * self.DISTANCE_RATIO * 100

        animations = [('conditional', MOVE_ANIMATION % time)]
        # set all parameters and properties
        image_control.setImage(imageDetails['file'])
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
        self.NEXT_IMAGE_TIME = ScreensaverSettings.getWaitTime()
        self.ROWS_AND_COLUMNS = ScreensaverSettings.getGridswitchRowsColumns()
        self.RANDOM_ORDER = ScreensaverSettings.isGridswitchRandom()
        self.IMAGE_CONTROL_COUNT = self.ROWS_AND_COLUMNS ** 2
        self.FAST_IMAGE_COUNT = self.IMAGE_CONTROL_COUNT

    # Get how long to wait until the next image is shown
    def getNextImageTime(self):
        # Needs to be implemented in sub class
        return int(self.NEXT_IMAGE_TIME)

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

    def process_image(self, image_control, imageDetails):
        if not self.image_count < self.FAST_IMAGE_COUNT:
            FADE_OUT_ANIMATION = ('effect=fade start=100 end=0 time=%d condition=true' % self.EFFECT_TIME)
            animations = [('conditional', FADE_OUT_ANIMATION)]
            image_control.setAnimations(animations)
            xbmc.sleep(self.EFFECT_TIME)
        image_control.setImage(imageDetails['file'])
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
