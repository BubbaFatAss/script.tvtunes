# -*- coding: utf-8 -*-
#Modules General
from traceback import print_exc
import time
import os
import re
import random
#Modules XBMC
import xbmc
import xbmcgui
import sys
import xbmcvfs
import xbmcaddon

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
        # Start by processing the arguments into a list of parameters
        try:
            # parse sys.argv for params
            log( sys.argv[ 1 ] )
            try:
                self.params = dict( arg.split( "=" ) for arg in sys.argv[ 1 ].split( "&" ) )
            except:
                print_exc()
                self.params = dict( sys.argv[ 1 ].split( "=" ))
        except:
            # no params passed
            print_exc()
            self.params = {}
        
        # Load the other settings from the addon setting menu
        self.enable_custom_path = __addon__.getSetting("custom_path_enable")
        if self.enable_custom_path == "true":
            self.custom_path = __addon__.getSetting("custom_path")
    
    def isCustomPathEnabled(self):
        return self.enable_custom_path == 'true'
    
    def getCustomPath(self):
        return custom_path
    
    def getDownVolume(self):
        return self.params.get("downvolume", 0 )

    def isLoop(self):
        return self.params.get("loop", "false" ) == 'true'
    
    def isFade(self):
        return __addon__.getSetting("fade") == 'true'
    
    def isSmbEnabled(self):
        return self.params.get("smb", "false" ) == 'true'

    def getSmbUser(self):
        return self.params.get("user", "guest" )
    
    def getSmbPassword(self):
        return self.params.get("password", "guest" )
    
    def getThemeFileRegEx(self):
        fileTypes = "mp3" # mp3 is the default that is always supported
        if(__addon__.getSetting("wma") == 'true'):
            fileTypes = fileTypes + "|wma"
        if(__addon__.getSetting("flac") == 'true'):
            fileTypes = fileTypes + "|flac"
        return '(theme[ _A-Za-z0-9.-]*.(' + fileTypes + '))'
    
    def isShuffleThemes(self):
        return __addon__.getSetting("shuffle") == 'true'
    
    def isRandomStart(self):
        return __addon__.getSetting("random") == 'true'


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
            m = re.search(self.settings.getThemeFileRegEx(), aFile)
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
        self.base_volume = self.getVolume()
        
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
        if self.loud:
            self.raiseVolume()
        # restore repeat state
        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 0, "repeat": "%s" }, "id": 1 }' % self.repeat)

    def stop(self):
        log("Player: stop called")
        xbmc.Player.stop(self)
        self.restoreSettings()

    def play(self, item=None, listitem=None, windowed=False):
        # if something is already playing, then we do not want
        # to replace it with the theme
        if not self.isPlaying():
            if not self.loud:
                self.lowerVolume()

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
            self.base_volume = self.getVolume()
            self.loud = True
            vol = ((60+self.base_volume-int( self.settings.getDownVolume()) )*(100/60.0))
            if vol < 0 : vol = 0
            log( "Player: volume goal: %s%% " % vol )
            xbmc.executebuiltin('XBMC.SetVolume(%d)' % vol, True)
            log( "Player: down volume to %d%%" % vol )
        except:
            print_exc()

    def raiseVolume( self ):
        self.base_volume = self.getVolume()
        vol = ((60+self.base_volume+int( self.settings.getDownVolume()) )*(100/60.0))
        log( "Player: volume goal : %s%% " % vol )
        log( "Player: raise volume to %d%% " % vol )
        xbmc.executebuiltin( 'XBMC.SetVolume(%d)' % vol, True )
        self.loud = False

    # Graceful end of the playing, will fade if set to do so
    def endPlaying(self):
        if self.settings.isFade():
            cur_vol = self.getVolume()
            cur_vol_perc = 100 + (cur_vol * (100/60.0))
            vol_step = cur_vol_perc / 10
            # do not mute completely else the mute icon shows up
            for step in range (0,9):
                vol = cur_vol_perc - vol_step
                log( "Player: fade_vol: %s" % str(vol) )
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
    def isVideoLibrary():
        return xbmc.getCondVisibility("Window.IsVisible(10025)")

    @staticmethod
    def isMovieInformation():
        return xbmc.getCondVisibility("Window.IsVisible(12003)")

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

###############################################################
# Class to make it easier to see the current state of TV Tunes
###############################################################
class TvTunesStatus():
    @staticmethod
    def isRunning():
        return xbmcgui.Window( 10025 ).getProperty("TvTunesIsRunning") == "true"

    @staticmethod
    def setRunningState(state):
        if state:
            xbmcgui.Window( 10025 ).setProperty( "TvTunesIsRunning", "true" )
        else:
            xbmcgui.Window( 10025 ).clearProperty('TvTunesIsRunning')

    @staticmethod
    def isAlive():
        return xbmc.getInfoLabel( "Window(10025).Property(TvTunesIsAlive)" ) == "true"
    
    @staticmethod
    def setAliveState(state):
        if state:
            xbmcgui.Window( 10025 ).setProperty( "TvTunesIsAlive", "true" )
        else:
            xbmcgui.Window( 10025 ).clearProperty('TvTunesIsAlive')


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
            isStartedDueToInfoScreen = False
            while (not self._stop):           # the code
                # We only stop looping and exit this script if we leave the Video library
                # We get called when we enter the library, and the only times we will end
                # will be if:
                # 1) A Video is selected to play
                # 2) We exit to the main menu away from the video view
                if not WindowShowing.isVideoLibrary():
                    log("Video Library no longer visible")
                    self.stop()
                
                if WindowShowing.isMovieInformation() and not self.themePlayer.isPlaying() and "plugin://" not in xbmc.getInfoLabel( "ListItem.Path" ) and not xbmc.getInfoLabel( "container.folderpath" ) == "videodb://5/":
                    isStartedDueToInfoScreen = True

                if isStartedDueToInfoScreen or WindowShowing.isSeasons() or WindowShowing.isEpisodes() and not self.themePlayer.isPlaying() and "plugin://" not in xbmc.getInfoLabel( "ListItem.Path" ) and not xbmc.getInfoLabel( "container.folderpath" ) == "videodb://5/":
                    if self.settings.isCustomPathEnabled() and not WindowShowing.isMovies():
                        tvshow = xbmc.getInfoLabel( "ListItem.TVShowTitle" ).replace(":","")
                        tvshow = normalize_string( tvshow )
                        self.newpath = os.path.join(self.settings.getCustomPath(), tvshow).decode("utf-8")
                    elif WindowShowing.isMovieInformation() and xbmc.getInfoLabel( "container.folderpath" ) == "videodb://2/2/":
                        self.newpath = xbmc.getInfoLabel( "ListItem.FilenameAndPath" )
                    else:
                        self.newpath = xbmc.getInfoLabel( "ListItem.Path" )
                    if not self.newpath == self.oldpath and not self.newpath == "" and not self.newpath == "videodb://2/2/":
                        log( "TunesBackend: old path: %s" % self.oldpath )
                        log( "TunesBackend: new path: %s" % self.newpath )
                        self.oldpath = self.newpath
                        if not self.themePlayer.isPlaying():
                            self.start_playing()
                        else:
                            log( "TunesBackend: player already playing" )

                if TvTunesStatus.isAlive() and not self.themePlayer.isPlaying():
                    log( "TunesBackend: playing ends" )
                    self.themePlayer.restoreSettings()
                    TvTunesStatus.setAliveState(False)

                if (WindowShowing.isTvShows() or WindowShowing.isMovies() ) and self.playpath and not WindowShowing.isMovieInformation():
                    isStartedDueToInfoScreen = False
                    log( "TunesBackend: reinit condition" )
                    self.newpath = ""
                    self.oldpath = ""
                    self.playpath = ""
                    log( "TunesBackend: end playing" )
                    self.themePlayer.endPlaying()
                    TvTunesStatus.setAliveState(False)

                if (xbmc.getInfoLabel( "container.folderpath" ) == "videodb://2/2/") or (WindowShowing.isMovies() and not WindowShowing.isMovieInformation()):
                    # clear the last tune path if we are back at the root of the tvshow library
                    self.prevplaypath = ""

                time.sleep( .5 )

        except:
            print_exc()
            self.stop()


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
        TvTunesStatus.setRunningState(False)

        # If currently playing a video file, then we have been overridden,
        # and we need to restore all the settings, the player callbacks
        # will not be called, so just force it on stop
        self.themePlayer.restoreSettings()

        log( "TunesBackend: ### Stopped TvTunes Backend ###" )
        self._stop = True


#########################
# Main
#########################


#if WindowShowing.isMovieInformation():
#    log( "### isMovieInformation ###" )

#if WindowShowing.isMovies():
#    log( "### isMovies ###" )


# TODO - need to maybe loop for a bit to see if something has started?
# how to stop 2 instances running at the same time?

# Make sure that we are not already running on another thread
# we do not want two running at the same time
if TvTunesStatus.isRunning() != True:
    # Record that the program has started running
    TvTunesStatus.setRunningState(True)

    # create the thread to run the program in
    main = TunesBackend()
    # start the thread
    main.run()
else:
    log("Already Running")


