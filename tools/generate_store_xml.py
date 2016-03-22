#
# Things to do before uploading themes
# 1) Make sure all themes are in mp3 format
# 2) Remove all tags etc from the mp3 file
# 3) Generate Replay Gain for each file
#
import sys
import os
import re
import urllib2
import xml.etree.ElementTree as ET
from xml.dom import minidom

import json


def isVideoFile(filename):
    if filename.endswith('.mp4'):
        return True
    if filename.endswith('.mkv'):
        return True
    if filename.endswith('.avi'):
        return True
    if filename.endswith('.mov'):
        return True
    return False


# Return a pretty-printed XML string for the Element.
def prettify(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    uglyXml = reparsed.toprettyxml(indent="    ")
    text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)
    return text_re.sub('>\g<1></', uglyXml)


class InfoXml():
    def __init__(self, tvdb_api_key='2B8557E0CBF7D720', tmdb_api_key='f7f51775877e0bb6703520952b3c7840'):
        self.tvdb_api_key = tvdb_api_key
        self.tvdb_url_prefix = 'http://thetvdb.com/api'
        self.lang = 'en'
        self.tmdb_api_key = tmdb_api_key
        self.tmdb_url_prefix = 'http://api.themoviedb.org/3'

    def generateTvShowInfo(self, showId, dir):
        infoFilename = os.path.join(dir, 'info.xml')

        # Check if the XML file already exists
        # TODO, read the data out of the file
        if os.path.isfile(infoFilename):
            return

        # Get the information for this TV Show
        (tvdbId, imdbId, name) = self.getTVDB_info(showId)

        # Check to see if a match was found
        if (tvdbId not in [None, ""]) or (imdbId not in [None, ""]) or (name not in [None, ""]):
            # Construct the XML handler
            root = ET.Element('info')
            if tvdbId not in [None, ""]:
                tvdbElem = ET.SubElement(root, 'tvdb')
                tvdbElem.text = tvdbId
            if imdbId not in [None, ""]:
                imdbElem = ET.SubElement(root, 'imdb')
                imdbElem.text = imdbId
            if name not in [None, ""]:
                nameElem = ET.SubElement(root, 'name')
                nameElem.text = name

            # Now create the file for the Store
            fileContent = prettify(root)

            recordFile = open(infoFilename, 'w')
            recordFile.write(fileContent)
            recordFile.close()

    def generateMovieInfo(self, movieId, dir):
        infoFilename = os.path.join(dir, 'info.xml')

        # Check if the XML file already exists
        # TODO, read the data out of the file
        if os.path.isfile(infoFilename):
            return

        # Get the information for this TV Show
        (tmdbId, imdbId, name) = self.getTMDB_info(movieId)

        # Check to see if a match was found
        if (imdbId not in [None, ""]) or (imdbId not in [None, ""]) or (name not in [None, ""]):
            # Construct the XML handler
            root = ET.Element('info')
            if tmdbId not in [None, ""]:
                tvdbElem = ET.SubElement(root, 'tmdb')
                tvdbElem.text = tmdbId
            if imdbId not in [None, ""]:
                imdbElem = ET.SubElement(root, 'imdb')
                imdbElem.text = imdbId
            if name not in [None, ""]:
                nameElem = ET.SubElement(root, 'name')
                nameElem.text = name

            # Now create the file for the Store
            fileContent = prettify(root)

            recordFile = open(infoFilename, 'w')
            recordFile.write(fileContent)
            recordFile.close()

    # Get the imdb id from the tvdb id
    def getTVDB_info(self, id):
        # http://thetvdb.com/api/2B8557E0CBF7D720/series/75565/en.xml
        url = '%s/%s/series/%s/en.xml' % (self.tvdb_url_prefix, self.tvdb_api_key, id)
        resp_details = self._makeCall(url)

        tvdbId = None
        imdbId = None
        name = None
        # The response is XML
        if resp_details not in [None, ""]:
            respData = ET.ElementTree(ET.fromstring(resp_details))

            rootElement = respData.getroot()
            if rootElement not in [None, ""]:
                if rootElement.tag == 'Data':
                    series = rootElement.findall('Series')
                    # Only want to process anything if there is just a single series
                    if (series not in [None, ""]) and (len(series) > 0):
                        # There should only be one series as we selected by Id
                        selectedSeries = series[0]

                        if selectedSeries not in [None, ""]:
                            tvdbIdElem = selectedSeries.find('id')
                            if tvdbIdElem not in [None, ""]:
                                tvdbId = tvdbIdElem.text
                            imdbIdElem = selectedSeries.find('IMDB_ID')
                            if imdbIdElem not in [None, ""]:
                                imdbId = imdbIdElem.text
                            nameElem = selectedSeries.find('SeriesName')
                            if nameElem not in [None, ""]:
                                name = nameElem.text
        else:
            print "Unable to find %s" % id

        return (tvdbId, imdbId, name)

    def getTMDB_info(self, id):
        url = "%s/%s/%s?api_key=%s" % (self.tmdb_url_prefix, 'movie', id, self.tmdb_api_key)
        json_details = self._makeCall(url)

        tmdb_id = None
        imdb_id = None
        name = None
        if json_details not in [None, ""]:
            json_response = json.loads(json_details)

            # The results of the search come back as an array of entries
            if 'id' in json_response:
                tmdb_id = json_response.get('id', None)
                if tmdb_id not in [None, ""]:
                    tmdb_id = str(tmdb_id)

            if 'imdb_id' in json_response:
                imdb_id = json_response.get('imdb_id', None)
                if imdb_id not in [None, ""]:
                    imdb_id = str(imdb_id)

            if 'title' in json_response:
                name = json_response.get('title', None)
                if name not in [None, ""]:
                    name = str(name)

        return (tmdb_id, imdb_id, name)

    # Perform the API call
    def _makeCall(self, url):
        resp_details = None
        try:
            req = urllib2.Request(url)
            req.add_header('Accept', 'application/json')
            response = urllib2.urlopen(req)
            resp_details = response.read()
            try:
                response.close()
            except:
                pass
        except:
            pass

        return resp_details


##################################
# Main of the TvTunes Service
##################################
if __name__ == '__main__':
    print "About to generate tvtunes-store.xml"

    shouldOpenWindows = False

    # Construct the XML handler
    root = ET.Element('tvtunesStore')
    enabledElem = ET.SubElement(root, 'enabled')
    enabledElem.text = "true"
    tvshowsElem = ET.SubElement(root, 'tvshows')
    moviesElem = ET.SubElement(root, 'movies')

    # Now add each tv show into the list
    tvShowIds = []
    if os.path.exists('tvshows'):
        tvShowIds = os.listdir('tvshows')

    print "Number of TV Shows is %d" % len(tvShowIds)
    openWindows = 0

    infoXml = InfoXml()

    for tvShowId in tvShowIds:
        # Get the contents of the directory
        themesDir = "%s/%s" % ('tvshows', tvShowId)
        themes = os.listdir(themesDir)

        # Remove any info.xml files
        if 'info.xml' in themes:
            themes.remove('info.xml')

        # Make sure the themes are not empty
        if len(themes) < 1:
            print "No themes in directory: %s" % themesDir
            continue

        # Create an element for this tv show
        tvshowElem = ET.SubElement(tvshowsElem, 'tvshow')
        tvshowElem.attrib['id'] = tvShowId

        # Generate the XML for the given TV Show
        infoXml.generateTvShowInfo(tvShowId, themesDir)

        numThemes = 0
        # Add each theme to the element
        for theme in themes:
            fullThemePath = "%s/%s" % (themesDir, theme)
            # Get the size of this theme file
            statinfo = os.stat(fullThemePath)
            fileSize = statinfo.st_size
            # Make sure not too small
            if fileSize < 19460:
                print "Themes file %s/%s is very small" % (themesDir, theme)
                continue

            themeElem = None
            # Add the theme to the list
            if isVideoFile(theme):
                print "Video Theme for %s is %s" % (themesDir, theme)
                themeElem = ET.SubElement(tvshowElem, 'videotheme')
            else:
                numThemes = numThemes + 1
                if not theme.endswith('.mp3'):
                    print "Audio theme %s is not mp3: %s" % (themesDir, theme)
                themeElem = ET.SubElement(tvshowElem, 'audiotheme')
            themeElem.text = theme
            themeElem.attrib['size'] = str(fileSize)

        if numThemes > 1:
            print "TvShow %s has %d themes" % (themesDir, numThemes)
            if shouldOpenWindows and (openWindows < 10):
                windowsDir = "start %s\\%s" % ('tvshows', tvShowId)
                os.system(windowsDir)
                openWindows = openWindows + 1

    # Now add each tv show into the list
    movieIds = []
    if os.path.exists('movies'):
        movieIds = os.listdir('movies')

    print "Number of Movies is %d" % len(movieIds)

    for movieId in movieIds:
        # Get the contents of the directory
        themesDir = "%s/%s" % ('movies', movieId)
        themes = os.listdir(themesDir)

        # Remove any info.xml files
        if 'info.xml' in themes:
            themes.remove('info.xml')

        # Make sure the themes are not empty
        if len(themes) < 1:
            print "No themes in directory: %s" % themesDir
            continue

        # Create an element for this tv show
        movieElem = ET.SubElement(moviesElem, 'movie')
        movieElem.attrib['id'] = movieId

        # Generate the XML for the given TV Show
        infoXml.generateMovieInfo(movieId, themesDir)

        numThemes = 0
        # Add each theme to the element
        for theme in themes:
            fullThemePath = "%s/%s" % (themesDir, theme)
            # Get the size of this theme file
            statinfo = os.stat(fullThemePath)
            fileSize = statinfo.st_size
            # Make sure not too small
            if fileSize < 19460:
                print "Themes file %s/%s is very small" % (themesDir, theme)
                continue

            themeElem = None
            # Add the theme to the list
            if isVideoFile(theme):
                if fileSize > 104857600:
                    print "Themes file %s/%s is very large" % (themesDir, theme)
                    continue
                print "Video Theme for %s is %s" % (themesDir, theme)
                themeElem = ET.SubElement(movieElem, 'videotheme')
            else:
                if fileSize > 20971520:
                    print "Themes file %s/%s is very large" % (themesDir, theme)
                    continue
                numThemes = numThemes + 1
                if not theme.endswith('.mp3'):
                    print "Audio theme %s is not mp3: %s" % (themesDir, theme)
                themeElem = ET.SubElement(movieElem, 'audiotheme')
            themeElem.text = theme
            themeElem.attrib['size'] = str(fileSize)

        if numThemes > 1:
            print "Movie %s has %d themes" % (themesDir, numThemes)
            if shouldOpenWindows and (openWindows < 10):
                windowsDir = "start %s\\%s" % ('movies', movieId)
                os.system(windowsDir)
                openWindows = openWindows + 1

    del infoXml

    # Now create the file for the Store
    fileContent = prettify(root)

    recordFile = open('tvtunes-store.xml', 'w')
    recordFile.write(fileContent)
    recordFile.close()
