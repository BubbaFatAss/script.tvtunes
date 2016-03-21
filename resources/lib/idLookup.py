# -*- coding: utf-8 -*-
import sys
import urllib
import urllib2
import traceback
import xml.etree.ElementTree as ET
import xbmc

if sys.version_info >= (2, 7):
    import json
else:
    import simplejson as json

from settings import log


# Method to look up the ID used to represent the given Movie or TV Show
def idLookup(name, year='', isTvShow=None):
    idDetails = {'imdb': None, 'tmdb': None, 'tvdb': None}
    if isTvShow is True:
        tvShowLookup = TvShowLookup()
        (tvdbId, imdbId) = tvShowLookup.getShowIds(name, str(year))
        idDetails['tvdb'] = tvdbId
        idDetails['imdb'] = imdbId
        del tvShowLookup

    elif isTvShow is False:
        movieLookup = MovieLookup()
        # Make the initial call with the year included
        idDetails['tmdb'] = movieLookup.getTMDB_by_name(name, str(year))
        # Check to see if a match was found
        if (idDetails['tmdb'] in [None, ""]) and (year not in [None, "", "0"]):
            # No match was found, so try without the year
            idDetails['tmdb'] = movieLookup.getTMDB_by_name(name)

        # Check if we have the tmdb id, if we do, then we need to also
        # get the imdb_id
        if idDetails['tmdb'] not in [None, ""]:
            idDetails['imdb'] = movieLookup.getTMDB_imdb_id(idDetails['tmdb'])

        # Check if we already have the imdb_id, if not, do another lookup
        if idDetails['imdb'] in [None, ""]:
            idDetails['imdb'] = movieLookup.getIMDB_id(name, str(year))

            # Check to see if a match was found
            if (idDetails['imdb'] in [None, ""]) and (year not in [None, "", "0"]):
                # No match was found, so try without the year
                idDetails['imdb'] = movieLookup.getIMDB_id(name)

        del movieLookup
    else:
        # Don't know if it is a Movie or TV Show, so check need to check both
        pass

    return idDetails


class MovieLookup():
    def __init__(self, api_key='f7f51775877e0bb6703520952b3c7840'):
        self.api_key = api_key
        self.tmdb_url_prefix = 'http://api.themoviedb.org/3'
        self.imdb_url_prefix = 'http://www.omdbapi.com/'
        self.lang = xbmc.getLanguage(xbmc.ISO_639_1)

    def __clean_name(self, mystring):
        newstring = ''
        for word in mystring.split(' '):
            if word.isalnum() is False:
                w = ""
                for i in range(len(word)):
                    if(word[i].isalnum()):
                        w += word[i]
                word = w
            newstring += ' ' + word
        return newstring.strip()

    def getTMDB_by_name(self, name, year=''):
        clean_name = urllib2.quote(self.__clean_name(name))
        query = 'query=%s' % clean_name

        if year not in [None, '']:
            query = '%s&year=%s' % (query, str(year))

        url = "%s/%s?language=%s&api_key=%s&%s" % (self.tmdb_url_prefix, 'search/movie', self.lang, self.api_key, query)
        json_details = self._makeCall(url)

        id = None
        if json_details not in [None, ""]:
            json_response = json.loads(json_details)

            # The results of the search come back as an array of entries
            if 'results' in json_response:
                for result in json_response['results']:
                    id = result.get('id', None)
                    if id not in [None, ""]:
                        id = str(id)
                        log("MovieLookup: Found matching Id %s" % str(id))
                        # Only getting the first match
                        break
            else:
                log("MovieLookup: No results returned")

        return id

    # Need to make a different call to get the IMDB, can not go straight from
    # name to imdb Id
    def getTMDB_imdb_id(self, tmdb_id):
        log("MovieLookup: Getting IMDB Id from TMDB Id %s" % tmdb_id)

        url = "%s/%s/%s?api_key=%s" % (self.tmdb_url_prefix, 'movie', tmdb_id, self.api_key)
        json_details = self._makeCall(url)

        imdb_id = None
        if json_details not in [None, ""]:
            json_response = json.loads(json_details)

            # The results of the search come back as an array of entries
            if 'imdb_id' in json_response:
                imdb_id = json_response.get('imdb_id', None)
                if imdb_id not in [None, ""]:
                    imdb_id = str(imdb_id)
                    log("MovieLookup: Found imdb Id %s from tmdb" % str(imdb_id))
            else:
                log("MovieLookup: No results returned for tmdb search for imdb id")

        return imdb_id

    # Need to make a different call to get the IMDB, can not go straight from
    # name to imdb Id
    def getTMDB_id_from_imdb_id(self, imdb_id):
        log("MovieLookup: Getting IMDB Id from TMDB Id %s" % imdb_id)

        # Use the same request for tmdb as imdb
        url = "%s/%s/%s?api_key=%s" % (self.tmdb_url_prefix, 'movie', imdb_id, self.api_key)
        json_details = self._makeCall(url)

        tmdb_id = None
        if json_details not in [None, ""]:
            json_response = json.loads(json_details)

            # The results of the search come back as an array of entries
            if 'id' in json_response:
                tmdb_id = json_response.get('id', None)
                if tmdb_id not in [None, ""]:
                    tmdb_id = str(tmdb_id)
                    log("MovieLookup: Found tmdb Id %s from imdb" % str(tmdb_id))
            else:
                log("MovieLookup: No results returned for tmdb search for tmdb from imdb id")

        return tmdb_id

    # Get the ID from imdb
    def getIMDB_id(self, name, year=''):
        clean_name = urllib2.quote(name)
        query = '?t=%s' % clean_name

        if year not in [None, '']:
            query = '%s&y==%s' % (query, str(year))

        url = "%s%s" % (self.imdb_url_prefix, query)
        json_details = self._makeCall(url)

        imdb_id = None
        if json_details not in [None, ""]:
            json_response = json.loads(json_details)

            if json_response.get('Response', 'False') == 'True':
                if 'imdbID' in json_response:
                    imdb_id = json_response.get('imdbID', None)
                    if imdb_id not in [None, ""]:
                        imdb_id = str(imdb_id)
                        log("MovieLookup: Found imdb Id %s" % str(imdb_id))
            else:
                log("MovieLookup: No results returned for imdb id search")

        return imdb_id

    # Perform the API call
    def _makeCall(self, url):
        log("MovieLookup: Making query using %s" % url)
        json_details = None
        try:
            req = urllib2.Request(url)
            req.add_header('Accept', 'application/json')
            response = urllib2.urlopen(req)
            json_details = response.read()
            try:
                response.close()
                log("MovieLookup: Request returned %s" % json_details)
            except:
                pass
        except:
            log("MovieLookup: Failed to retrieve details from %s: %s" % (url, traceback.format_exc()))

        return json_details


class TvShowLookup():
    def __init__(self, api_key='2B8557E0CBF7D720'):
        self.api_key = api_key
        self.tvdb_url_prefix = 'http://thetvdb.com/api'
        self.lang = xbmc.getLanguage(xbmc.ISO_639_1)
        self.mirror_url = "http://thetvdb.com"

    def getShowIds(self, name, year=''):
        searchName = name
        try:
            if type(searchName) == type(u''):
                searchName = searchName.encode('utf-8')
        except:
            pass

        get_args = {'seriesname': searchName, 'language': self.lang}

        get_args = urllib.urlencode(get_args, doseq=True)
        # Details of the data returned detailed at the following location
        # http://www.thetvdb.com/wiki/index.php?title=API:GetSeries
        url = "%s/GetSeries.php?%s" % (self.tvdb_url_prefix, get_args)
        resp_details = self._makeCall(url)

        tvdbId = None
        imdbId = None
        # The response is XML
        if resp_details not in [None, ""]:
            try:
                respData = ET.ElementTree(ET.fromstring(resp_details))

                rootElement = respData.getroot()
                if rootElement not in [None, ""]:
                    if rootElement.tag == 'Data':
                        series = rootElement.findall('Series')
                        # Only want to process anything if there is just a single series
                        if (series not in [None, ""]) and (len(series) > 0):
                            selectedSeries = None
                            # If there is a year, we might be able to filter to a single entry
                            if (len(series) > 1) and (year not in [None, "", "0"]):
                                for entry in series:
                                    firstAiredElm = entry.find('FirstAired')
                                    if firstAiredElm not in [None, ""]:
                                        firstAired = firstAiredElm.text
                                        if firstAired not in [None, ""]:
                                            if year in firstAired:
                                                selectedSeries = entry
                                                break
                            else:
                                selectedSeries = series[0]

                            if selectedSeries not in [None, ""]:
                                tvdbIdElem = selectedSeries.find('seriesid')
                                if tvdbIdElem not in [None, ""]:
                                    tvdbId = tvdbIdElem.text
                                    log("TvShowLookup: Found seriesid = %s" % tvdbId)

                                imdbIdElem = selectedSeries.find('IMDB_ID')
                                if imdbIdElem not in [None, ""]:
                                    imdbId = imdbIdElem.text
                                    log("TvShowLookup: Found IMDB_ID = %s" % imdbId)
            except:
                log("TvShowLookup: Failed to process data %s: %s" % (resp_details, traceback.format_exc()))

        return (tvdbId, imdbId)

    # Get the imdb id from the tvdb id
    def getImdbId_from_tvdbId(self, imdbId):
        # http://thetvdb.com/api/2B8557E0CBF7D720/series/75565/en.xml
        url = '%s/%s/series/%s/en.xml' % (self.tvdb_url_prefix, self.api_key, imdbId)
        resp_details = self._makeCall(url)

        imdbId = None
        # The response is XML
        if resp_details not in [None, ""]:
            try:
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
                                imdbIdElem = selectedSeries.find('IMDB_ID')
                                if imdbIdElem not in [None, ""]:
                                    imdbId = imdbIdElem.text
                                    log("TvShowLookup: Found IMDB_ID = %s" % imdbId)
            except:
                log("TvShowLookup: Failed to process data %s: %s" % (resp_details, traceback.format_exc()))

        return imdbId

    # Perform the API call
    def _makeCall(self, url):
        log("TvShowLookup: Making query using %s" % url)
        resp_details = None
        try:
            req = urllib2.Request(url)
            req.add_header('Accept', 'application/json')
            response = urllib2.urlopen(req)
            resp_details = response.read()
            try:
                response.close()
                log("TvShowLookup: Request returned %s" % resp_details)
            except:
                pass
        except:
            log("TvShowLookup: Failed to retrieve details from %s: %s" % (url, traceback.format_exc()))

        return resp_details
