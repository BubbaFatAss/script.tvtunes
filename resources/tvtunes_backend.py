# -*- coding: utf-8 -*-
#Modules General
from traceback import print_exc
import os
import re
import random
import threading
from xml.etree.ElementTree import ElementTree
#Modules XBMC
import xbmc
import xbmcgui
import sys
import xbmcvfs
import xbmcaddon

# Add JSON support for queries
if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson


__addon__     = xbmcaddon.Addon(id='script.tvtunes')
__addonid__   = __addon__.getAddonInfo('id')

#
# Output logging method, if global logging is enabled
#
def log(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (__addonid__, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)


def normalize_string( text ):
    try: text = unicodedata.normalize( 'NFKD', _unicode( text ) ).encode( 'ascii', 'ignore' )
    except: pass
    return text

##############################
# Stores Various Settings
##############################
class Settings():
    def __init__( self ):
        # Load the other settings from the addon setting menu
        self.downvolume = __addon__.getSetting("downvolume")
        self.downvolume = self.downvolume.split(",")[0]
        self.downvolume = self.downvolume.split(".")[0]
        
        self.enable_custom_path = __addon__.getSetting("custom_path_enable")
        if self.enable_custom_path == "true":
            self.custom_path = __addon__.getSetting("custom_path")
        self.themeRegEx = self.loadThemeFileRegEx()
        self.screensaverTime = self.loadScreensaverSettings()


    # Loads the Screensaver settings
    # In Frodo there is no way to get the time before the screensaver
    # is set to start, this means that the only way open to us is to
    # load up the XML config file and read it from there.
    # One of the many down sides of this is that the XML file will not
    # be updated to reflect changes until the user exits XMBC
    # This isn't a big problem as screensaver times are not changed
    # too often
    #
    # Unfortunately the act of stopping the theme is seem as "activity"
    # so it will reset the time, in Gotham, there will be a way to
    # actually start the screensaver again, but until then there is
    # not mush we can do
    def loadScreensaverSettings(self):
        screenTimeOutSeconds = -1
        pguisettings = xbmc.translatePath('special://profile/guisettings.xml')

        log("Settings: guisettings.xml location = " + pguisettings)

        # Make sure we found the file and it exists
        if os.path.exists(pguisettings):
            # Create an XML parser
            elemTree = ElementTree()
            elemTree.parse(pguisettings)
            
            # First check to see if any screensaver is set
            isEnabled = elemTree.findtext('screensaver/mode')
            if (isEnabled == None) or (isEnabled == ""):
                log("Settings: No Screensaver enabled")
            else:
                log("Settings: Screensaver set to " + isEnabled)

                # Get the screensaver setting in minutes
                result = elemTree.findtext('screensaver/time')
                if result != None:
                    log("Settings: Screensaver timeout set to " + result)
                    # Convert from minutes to seconds, also reduce by 30 seconds
                    # as we want to ensure we have time to stop before the
                    # screensaver kicks in
                    screenTimeOutSeconds = (int(result) * 60) - 30
                else:
                    log("Settings: No Screensaver timeout found")
            
            del elemTree
        return screenTimeOutSeconds

    # Calculates the regular expression to use to search for theme files
    def loadThemeFileRegEx(self):
        fileTypes = "mp3" # mp3 is the default that is always supported
        if(__addon__.getSetting("wma") == 'true'):
            fileTypes = fileTypes + "|wma"
        if(__addon__.getSetting("flac") == 'true'):
            fileTypes = fileTypes + "|flac"
        if(__addon__.getSetting("m4a") == 'true'):
            fileTypes = fileTypes + "|m4a"
        if(__addon__.getSetting("wav") == 'true'):
            fileTypes = fileTypes + "|wav"
        return '(theme[ _A-Za-z0-9.-]*.(' + fileTypes + ')$)'

    def isCustomPathEnabled(self):
        return self.enable_custom_path == 'true'
    
    def getCustomPath(self):
        return self.custom_path
    
    def getDownVolume(self):
        return self.downvolume

    def isLoop(self):
        return __addon__.getSetting("loop") == 'true'
    
    def isFadeOut(self):
        return __addon__.getSetting("fadeOut") == 'true'

    def isFadeIn(self):
        return __addon__.getSetting("fadeIn") == 'true'
    
    def isSmbEnabled(self):
        if __addon__.getSetting("smb_share"):
            return True
        else:
            return False

    def getSmbUser(self):
        if __addon__.getSetting("smb_login"):
            return __addon__.getSetting("smb_login")
        else:
            return "guest"
    
    def getSmbPassword(self):
        if __addon__.getSetting("smb_psw"):
            return __addon__.getSetting("smb_psw")
        else:
            return "guest"
    
    def getThemeFileRegEx(self):
        return self.themeRegEx
    
    def isShuffleThemes(self):
        return __addon__.getSetting("shuffle") == 'true'
    
    def isRandomStart(self):
        return __addon__.getSetting("random") == 'true'

    def isTimout(self):
        if self.screensaverTime == -1:
            return False
        # It is a timeout if the idle time is larger that the time stored
        # for when the screensaver is due to kick in
        if (xbmc.getGlobalIdleTime() > self.screensaverTime):
            log("Settings: Stopping due to screensaver")
            return True
        else:
            return False


##############################
# Calculates file locations
##############################
class ThemeFiles():
    def __init__(self, settings, rawPath):
        self.settings = settings
        self.rawPath = rawPath

    #
    # Gets the usable path after alterations like network details
    #
    def getUsablePath(self):
        workingPath = self.rawPath
        if self.settings.isSmbEnabled() and workingPath.startswith("smb://") : 
            log( "### Try authentication share" )
            workingPath = workingPath.replace("smb://", "smb://%s:%s@" % (self.settings.getSmbUser(), self.settings.getSmbPassword()) )
            log( "### %s" % workingPath )
    
        #######hack for episodes stored as rar files
        if 'rar://' in str(workingPath):
            workingPath = workingPath.replace("rar://","")
        
        return workingPath

    #
    # Calculates the location of the theme file
    #
    def getThemePlaylist(self):
        # Get the full path with any network alterations
        workingPath = self.getUsablePath()

        #######hack for TV shows stored as ripped disc folders
        if 'VIDEO_TS' in str(workingPath):
            log( "### FOUND VIDEO_TS IN PATH: Correcting the path for DVDR tv shows" )
            workingPath = self._updir( workingPath, 3 )
            playlist = self.getThemeFiles(workingPath)
            if playlist.size() < 1:
                workingPath = self._updir(workingPath,1)
                playlist = self.getThemeFiles(workingPath)
        #######end hack
        else:
            playlist = self.getThemeFiles(workingPath)
            # If no theme files were found in this path, look at the parent directory
            if playlist.size() < 1:
                workingPath = os.path.dirname( os.path.dirname( workingPath ))
                playlist = self.getThemeFiles(workingPath)

        log("ThemeFiles: Playlist size = " + str(playlist.size()))
        log("ThemeFiles: Working Path = " + workingPath)
        
        return (workingPath, playlist)

    def _updir(self, thepath, x):
        # move up x directories on the path
        while x > 0:
            x -= 1
            thepath = (os.path.split(thepath))[0]
        return thepath

    # Search for theme files in the given directory
    def getThemeFiles(self, directory):
        log( "Searching " + directory + " for " + self.settings.getThemeFileRegEx() )
        dirs, files = xbmcvfs.listdir( directory )
        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        playlist.clear()
        for aFile in files:
            m = re.search(self.settings.getThemeFileRegEx(), aFile, re.IGNORECASE)
            if m:
                path = os.path.join( directory, aFile )
                log("ThemeFiles: Found match: " + path)
                # If there are any files matching the RegEx, add them to a playlist
                playlist.add( url=path )

        if self.settings.isShuffleThemes() and playlist.size() > 1:
            playlist.shuffle()

        return playlist


###################################
# Custom Player to play the themes
###################################
class Player(xbmc.Player):
    def __init__(self, settings, *args):
        self.settings = settings
        self.loud = False
        # Save the volume from before any alterations
        self.original_volume = self.getVolume()
        
        # Save off the current repeat state before we started playing anything
        if xbmc.getCondVisibility('Playlist.IsRepeat'):
            self.repeat = "all"
        elif xbmc.getCondVisibility('Playlist.IsRepeatOne'):
            self.repeat = "one"
        else:
            self.repeat = "off"

        xbmc.Player.__init__(self, *args)
        
    def onPlayBackStopped(self):
        log("Player: Received onPlayBackStopped")
        self.restoreSettings()
        xbmc.Player.onPlayBackStopped(self)

    def onPlayBackEnded(self):
        log("Player: Received onPlayBackEnded")
        self.restoreSettings()
        xbmc.Player.onPlayBackEnded(self)

    def restoreSettings(self):
        log("Player: Restoring player settings" )
        while self.isPlayingAudio():
            xbmc.sleep(1)
        # restore repeat state
        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 0, "repeat": "%s" }, "id": 1 }' % self.repeat)
        # Force the volume to the starting volume
        pre_vol_perc = 100 + (self.original_volume * (100/60.0))
        xbmc.executebuiltin('XBMC.SetVolume(%d)' % pre_vol_perc, True)


    def stop(self):
        log("Player: stop called")
        # Only stop if playing audio
        if self.isPlayingAudio():
            xbmc.Player.stop(self)
        self.restoreSettings()

    def play(self, item=None, listitem=None, windowed=False):
        # if something is already playing, then we do not want
        # to replace it with the theme
        if not self.isPlaying():
            if not self.loud:
                self.lowerVolume()

            if self.settings.isFadeIn():
                # Get the current volume - this is out target volume
                targetVol = self.getVolume()
                cur_vol_perc = 1
                vol_step = (100 + (targetVol * (100/60.0))) / 10
                # Reduce the volume before starting
                # do not mute completely else the mute icon shows up
                xbmc.executebuiltin('XBMC.SetVolume(1)', True)
                # Now start playing before we start increasing the volume
                xbmc.Player.play(self, item=item, listitem=listitem, windowed=windowed)
                # Wait until playing has started
                while not self.isPlayingAudio():
                    xbmc.sleep(30)

                for step in range (0,9):
                    vol = cur_vol_perc + vol_step
                    log( "Player: fadeIn_vol: %s" % str(vol) )
                    xbmc.executebuiltin('XBMC.SetVolume(%d)' % vol, True)
                    cur_vol_perc = vol
                    xbmc.sleep(200)
                # Make sure we end on the correct volume
                xbmc.executebuiltin('XBMC.SetVolume(%d)' % ( 100 + (targetVol *(100/60.0))), True)
            else:
                xbmc.Player.play(self, item=item, listitem=listitem, windowed=windowed)


            if self.settings.isLoop():
                xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 0, "repeat": "all" }, "id": 1 }')
            else:
                xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 0, "repeat": "off" }, "id": 1 }')
            
            if self.settings.isRandomStart():
                random.seed()
                randomStart = random.randint( 0, int(xbmc.Player().getTotalTime() * .75) )        
                log("Player: Setting Random start, Total Track = %s, Start Time = %s" % (xbmc.Player().getTotalTime(), randomStart))
                xbmc.Player().seekTime( randomStart )


    def getVolume(self):
        try:
            volume = int(xbmc.getInfoLabel('player.volume').split(".")[0])
        except:
            volume = int(xbmc.getInfoLabel('player.volume').split(",")[0])
        log( "Player: current volume: %s%%" % (( 60 + volume )*(100/60.0)) )
        return volume


    def lowerVolume( self ):
        try:
            current_volume = self.getVolume()
            self.loud = True
            vol = ((60+current_volume-int( self.settings.getDownVolume()) )*(100/60.0))
            if vol < 0 :
                vol = 0
            log( "Player: volume goal: %s%% " % vol )
            xbmc.executebuiltin('XBMC.SetVolume(%d)' % vol, True)
            log( "Player: down volume to %d%%" % vol )
        except:
            print_exc()

    # Graceful end of the playing, will fade if set to do so
    def endPlaying(self):
        if self.isPlayingAudio() and self.settings.isFadeOut():
            cur_vol = self.getVolume()
            cur_vol_perc = 100 + (cur_vol * (100/60.0))
            vol_step = cur_vol_perc / 10
            # do not mute completely else the mute icon shows up
            for step in range (0,9):
                # If the system is going to be shut down then we need to reset
                # everything as quickly as possible
                if WindowShowing.isShutdownMenu() or xbmc.abortRequested:
                    log("Player: Shutdown menu detected, cancelling fade")
                    break
                vol = cur_vol_perc - vol_step
                log( "Player: fadeOut_vol: %s" % str(vol) )
                xbmc.executebuiltin('XBMC.SetVolume(%d)' % vol, True)
                cur_vol_perc = vol
                xbmc.sleep(200)
            # need to stop before we turn the volume back up, however we
            # need to make sure if we have changed the volume, we save
            # of the loud setting so it can be re-applied after we recover
            # from the fade
            lastLoudSetting = self.loud
            self.stop()
            self.loud = lastLoudSetting
            # wait till player is stopped before raising the volume
            while self.isPlayingAudio():
                xbmc.sleep(50)
            pre_vol_perc = 100 + (cur_vol * (100/60.0))
            xbmc.executebuiltin('XBMC.SetVolume(%d)' % pre_vol_perc, True)
        # Need to always stop by the end of this
        self.stop()



###############################################################
# Class to make it easier to see which screen is being checked
###############################################################
class WindowShowing():
    @staticmethod
    def isHome():
        return xbmc.getCondVisibility("Window.IsVisible(home)")

    @staticmethod
    def isVideoLibrary():
        return xbmc.getCondVisibility("Window.IsVisible(videolibrary)")

    @staticmethod
    def isMovieInformation():
        return xbmc.getCondVisibility("Window.IsVisible(movieinformation)")

    @staticmethod
    def isTvShows():
        return xbmc.getCondVisibility("Container.Content(tvshows)")

    @staticmethod
    def isSeasons():
        return xbmc.getCondVisibility("Container.Content(Seasons)")

    @staticmethod
    def isEpisodes():
        return xbmc.getCondVisibility("Container.Content(Episodes)")

    @staticmethod
    def isMovies():
        return xbmc.getCondVisibility("Container.Content(movies)")

    @staticmethod
    def isScreensaver():
        return xbmc.getCondVisibility("System.ScreenSaverActive")

    @staticmethod
    def isShutdownMenu():
        return xbmc.getCondVisibility("Window.IsVisible(shutdownmenu)")

    @staticmethod
    def isRecentEpisodesAdded():
        return xbmc.getInfoLabel( "container.folderpath" ) == "videodb://5/"

    @staticmethod
    def isTvShowTitles():
        return xbmc.getInfoLabel( "container.folderpath" ) == "videodb://2/2/"

    @staticmethod
    def isPluginPath():
        return "plugin://" in xbmc.getInfoLabel( "ListItem.Path" )


###############################################################
# Class to make it easier to see the current state of TV Tunes
###############################################################
class TvTunesStatus():
    @staticmethod
    def isAlive():
        return xbmcgui.Window( 10025 ).getProperty( "TvTunesIsAlive" ) == "true"
    
    @staticmethod
    def setAliveState(state):
        if state:
            xbmcgui.Window( 10025 ).setProperty( "TvTunesIsAlive", "true" )
        else:
            xbmcgui.Window( 10025 ).clearProperty('TvTunesIsAlive')

    @staticmethod
    def clearRunningState():
        xbmcgui.Window( 10025 ).clearProperty('TvTunesIsRunning')

    # Check if the is a different version running
    @staticmethod
    def isOkToRun():
        # Get the current thread ID
        curThreadId = threading.currentThread().ident
        log("TvTunesStatus: Thread ID = " + str(curThreadId))

        # Check if the "running state" is set
        existingvalue = xbmcgui.Window( 10025 ).getProperty("TvTunesIsRunning")
        if existingvalue == "":
            log("TvTunesStatus: Current running state is empty, setting to " + str(curThreadId))
            xbmcgui.Window( 10025 ).setProperty( "TvTunesIsRunning", str(curThreadId) )
        else:
            # If it is check if it is set to this thread value
            if existingvalue != str(curThreadId):
                log("TvTunesStatus: Running ID already set to " + existingvalue)
                return False
        # Default return True unless we have a good reason not to run
        return True


#
# Thread to run the program back-end in
#
class TunesBackend( ):
    def __init__( self ):
        self.settings = Settings()
        self.themePlayer = Player(settings=self.settings)
        self._stop = False
        log( "### starting TvTunes Backend ###" )
        self.newpath = ""
        self.oldpath = ""
        self.playpath = ""
        self.prevplaypath = ""
        
    def run( self ):
        try:
            # Before we actually start playing something, make sure it is OK
            # to run, need to ensure there are not multiple copies running
            if not TvTunesStatus.isOkToRun():
                return

            while (not self._stop):
                # If shutdown is in progress, stop quickly (no fade out)
                if WindowShowing.isShutdownMenu() or xbmc.abortRequested:
                    self.stop()
                    break

                # We only stop looping and exit this script if we leave the Video library
                # We get called when we enter the library, and the only times we will end
                # will be if:
                # 1) A Video is selected to play
                # 2) We exit to the main menu away from the video view
                if not WindowShowing.isVideoLibrary() or WindowShowing.isScreensaver() or self.settings.isTimout():
                    log("TunesBackend: Video Library no longer visible")
                    # End playing cleanly (including any fade out) and then stop everything
                    self.themePlayer.endPlaying()
                    self.stop()
                    break

                if self.isPlayingZone() and not self.themePlayer.isPlaying():
                    self.newpath = self.getThemePath();

                # At this point we have several options
                # 1) The path is the same as it was last time, so leave playing what is currently playing
                # 2) The path has changed, but is still for the same theme - so leave playing
                # 3) The path has changed and now points to a new theme - start playing new theme
                # 4) The path no longer points to a theme - stop playing

                    if not self.newpath == self.oldpath and not self.newpath == "" and not self.newpath == "videodb://2/2/":
                        log( "TunesBackend: old path: %s" % self.oldpath )
                        log( "TunesBackend: new path: %s" % self.newpath )
                        self.oldpath = self.newpath
                        if not self.themePlayer.isPlaying():
                            self.start_playing()
                        else:
                            log( "TunesBackend: player already playing" )

                # This will occur when a theme has stopped playing, maybe is is not set to loop
                if TvTunesStatus.isAlive() and not self.themePlayer.isPlayingAudio():
                    log( "TunesBackend: playing ends" )
                    self.themePlayer.restoreSettings()
                    TvTunesStatus.setAliveState(False)

                # This is the case where the user has moved from within an area where the themes
                # to an area where the theme is no longer played, so it will trigger a stop and
                # reset everything to highlight that nothing is playing
                # Note: TvTunes is still running in this case, just not playing a theme
                if not self.isPlayingZone() and self.playpath:
                    log( "TunesBackend: reinit condition" )
                    self.newpath = ""
                    self.oldpath = ""
                    self.playpath = ""
                    log( "TunesBackend: end playing" )
                    self.themePlayer.endPlaying()
                    TvTunesStatus.setAliveState(False)

                # This is the case where we are looking at the lists of movies or TV Series
                if WindowShowing.isTvShowTitles() or (WindowShowing.isMovies() and not WindowShowing.isMovieInformation()):
                    # clear the last tune path if we are back at the root of the tvshow library
                    self.prevplaypath = ""

                xbmc.sleep(200)

        except:
            print_exc()
            self.stop()

    # Works out if the currently displayed area on the screen is something
    # that is deemed a zone where themes should be played
    def isPlayingZone(self):
        if WindowShowing.isRecentEpisodesAdded():
            return False
        if WindowShowing.isPluginPath():
            return False
        if WindowShowing.isMovieInformation():
            return True
        if WindowShowing.isSeasons():
            return True
        if WindowShowing.isEpisodes():
            return True
        # Any other area is deemed to be a non play area
        return False

    # Locates the path to look for a theme to play based on what is
    # currently being displayed on the screen
    def getThemePath(self):
        themePath = ""

        # Check if the files are stored in a custom path
        if self.settings.isCustomPathEnabled():
            if not WindowShowing.isMovies():
                videotitle = xbmc.getInfoLabel( "ListItem.TVShowTitle" )
            else:
                videotitle = xbmc.getInfoLabel( "ListItem.Title" )
            videotitle = normalize_string( videotitle.replace(":","") )
            themePath = os.path.join(self.settings.getCustomPath(), videotitle).decode("utf-8")

        # Looking at the TV Show information page
        elif WindowShowing.isMovieInformation() and WindowShowing.isTvShowTitles():
            themePath = xbmc.getInfoLabel( "ListItem.FilenameAndPath" )
        else:
            themePath = xbmc.getInfoLabel( "ListItem.Path" )

        return themePath


    def start_playing( self ):
        themefile = ThemeFiles(self.settings, self.newpath)
        self.playpath, playlist = themefile.getThemePlaylist()

        if playlist.size() > 0:
            if self.playpath == self.prevplaypath: 
                log( "TunesBackend: Not playing the same files twice %s" % self.playpath )
                return # don't play the same tune twice (when moving from season to episodes etc)
            self.prevplaypath = self.playpath
            TvTunesStatus.setAliveState(True)
            log( "TunesBackend: start playing %s" % self.playpath )
            self.themePlayer.play( playlist )
        else:
            log("TunesBackend: no themes found for %s" % self.newpath )


    def stop( self ):
        log( "TunesBackend: ### Stopping TvTunes Backend ###" )
        if TvTunesStatus.isAlive() and not self.themePlayer.isPlayingVideo(): 
            log( "TunesBackend: stop playing" )
            self.themePlayer.stop()
        while self.themePlayer.isPlayingAudio():
            xbmc.sleep(50)
        TvTunesStatus.setAliveState(False)
        TvTunesStatus.clearRunningState()

        # If currently playing a video file, then we have been overridden,
        # and we need to restore all the settings, the player callbacks
        # will not be called, so just force it on stop
        self.themePlayer.restoreSettings()

        log( "TunesBackend: ### Stopped TvTunes Backend ###" )
        self._stop = True


#########################
# Main
#########################


# Make sure that we are not already running on another thread
# we do not want two running at the same time
if TvTunesStatus.isOkToRun():
    # Create the main class to control the theme playing
    main = TunesBackend()

    # Start the themes running
    main.run()
else:
    log("TvTunes Already Running")


