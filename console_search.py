#Dependencies: tweepy, pyshp

import json, shapefile, time, math
from tweepy import Stream, OAuthHandler
from tweepy.streaming import StreamListener
from keys import keys

# Need to fixing encoding where convert  shapefile
import sys
reload(sys)
sys.setdefaultencoding('utf8')

#Variables that contains the user credentials to access Twitter API 
CONSUMER_KEY = keys['consumer_key']
CONSUMER_SECRET = keys['consumer_secret']
ACCESS_TOKEN = keys['access_token']
ACCESS_TOKEN_SECRET = keys['access_token_secret']

#User input
file_name = '20k_min'
max_tweets = 1
keywords = None #'#twitter, a, b, c'.split(',')
locations = [-180,-90,180,90]


def print_time(source, now, max, all):
    print source, ' | ', now, '/', max, ' |  Requests:', \
         all, " |  %ssec" % math.trunc(time.time() - start_time)


class listener(StreamListener):

    def on_data(self, data):
        if not hasattr(listener, '_geo_tweets'):
            open(file_name + '.geojson', 'w').write('{"type":"FeatureCollection","features":[') #clean file
            listener._all_tweets = 0 #from statictic
            listener._geo_tweets = 0
        
        open('last_' + file_name + '.json', 'w').write(data) # Last data - for debug
        jdata = json.loads(data)
        listener._all_tweets += 1

        if listener._all_tweets % 10 == 0:
            print_time('GeoJSON', listener._geo_tweets, max_tweets, listener._all_tweets)

        # Skip 'limit'-messages & non geotweets
        if 'limit' in jdata or \
                (not jdata['place'] and not jdata['geo']):
            return True


        # Write as geojson
        open(file_name + '.geojson', 'a').write('\n\t{ "type": "Geotweet", \n\t\t"geometry":\n\t\t\t')
        if not jdata['geo']: # Place
            # Change Polygon to Point
            coordinates = jdata['place']['bounding_box']['coordinates'][0]
            lon = (coordinates[0][0] + coordinates[2][0]) / 2
            lat = (coordinates[0][1] + coordinates[2][1]) / 2
            open(file_name + '.geojson', 'a').write('{"type": "Point", "coordinates": [' + \
                str(lon) + ', ' + str(lat) + ']}')
        else: # Geo
            open(file_name + '.geojson', 'a').write(str(jdata["geo"]).replace("u'", '"').replace("'", '"'))
        open(file_name + '.geojson', 'a').write(',\n\t\t"properties": \n\t\t\t' + data + '\t}')
        

        listener._geo_tweets += 1

        if listener._geo_tweets == max_tweets:
            open(file_name + '.geojson', 'a').write('\n]}')
            print_time('GeoJSON', listener._geo_tweets, max_tweets, listener._all_tweets)
            print 'GeoJSON: Done'
            return False
        
        open(file_name + '.geojson', 'a').write(',')
        return True

    def on_error(self, status):
        print 'ERROR ' + str(status)
        if status == 420:
            print 'Exceed a limit requests connect to' \
                + 'the streaming API in a window of time (15min)'
            return False  # Returning False in on_data disconnects the stream


auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

def run_stream(auth, locations=[-180,-90,180,90], keywords=''):
    stream = Stream(auth, listener())
    stream.filter(locations=locations, track=keywords)

start_time = time.time()
run_stream(auth, locations, keywords)

"""
Generate shapefile
"""

# function to generate .prj file information using spatialreference.org
def getWKT_PRJ (epsg_code):
     import urllib
     # access projection information
     wkt = urllib.urlopen('http://spatialreference.org/ref/epsg/{0}/prettywkt/'.format(epsg_code))
     remove_spaces = wkt.read().replace(' ','') # remove spaces between charachters
     output = remove_spaces.replace('\n', '') # place all the text on one line
     return output

start_time = time.time()
shp = shapefile.Writer(shapefile.POINT) # create a point shapefile

# for every record there must be a corresponding geometry.
shp.autoBalance = 1

# create the field names and data type for each.
field = [
        'created_at', 'id', 'id_str', 'text', 'source', 'truncated', \
        'in_reply_to_status_id', 'in_reply_to_status_id_str', \
        'in_reply_to_user_id', 'in_reply_to_user_id_str', \
        'in_reply_to_screen_name', 'geo', 'coordinates', \
        'place', 'contributors', 'is_quote_status', 'retweet_count', \
        'favorite_count', 'entities', 'favorited', 'retweeted', \
        'filter_level', 'lang', 'timestamp_ms'
        ]

for i in range(len(field)):
    shp.field(field[i].upper(), 'C')


# access the GeoJSON file
with open(file_name + '.geojson') as data_file:    
    reader = json.load(data_file)


#loop through each of the rows and assign the attributes to variables
a = {}
for tweet in range(max_tweets):
    longitude = reader['features'][tweet]['geometry']['coordinates'][0]
    latitude = reader['features'][tweet]['geometry']['coordinates'][1]

    for i in range(len(field)):
        a.update({field[i]: str(reader['features'][tweet]['properties'][field[i]])
                               .replace('\\', '').replace("u'", '').replace("'", '')})

    # create the point geometry
    shp.point(float(longitude), float(latitude))
    # add attribute data

    shp.record(\
        a['created_at'], a['id'], a['id_str'], a['text'], a['source'], a['truncated'], \
        a['in_reply_to_status_id'], a['in_reply_to_status_id_str'], \
        a['in_reply_to_user_id'], a['in_reply_to_user_id_str'], \
        a['in_reply_to_screen_name'], a['geo'], a['coordinates'], \
        a['place'], a['contributors'], a['is_quote_status'], a['retweet_count'], \
        a['favorite_count'], a['entities'], a['favorited'], a['retweeted'], \
        a['filter_level'], a['lang'], a['timestamp_ms']\
        )

    if (tweet + 1) % 1000 == 0:
        print_time('Shapefile', tweet + 1, max_tweets, max_tweets)


shp.save(file_name) # save the Shapefile

prj = open(file_name + '.prj', 'w') # create the .prj file
epsg = getWKT_PRJ('4326') # call the function and supply the epsg code
prj.write(epsg)
prj.close()
print 'Shapefile: Done'