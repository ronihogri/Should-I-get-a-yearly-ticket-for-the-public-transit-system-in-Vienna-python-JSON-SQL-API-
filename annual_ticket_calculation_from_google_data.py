'''
Roni Hogri, August 2023

The purpose of this program is to use Google location data to calculate whether a yearly ticket (Jahreskarte) in Vienna would have been cheaper 
than buying single-ride tickets for the selected period. 
This program is meant to run on the redacted json data created by the json_redact.py program. 

Note: For geodata processing, this program uses the website provided by Dr. Charles Severance, see:
http://py4e-data.dr-chuck.net/
This is a subset of data from the Google Geo Coding API - it does not require you to get a personal API key or pay any fees to Google.
'''

#user input:

threshold_P = 30 #threshold (in %) over which probability is high enough to be considered
#I found that P > 30% of public transit use usually meant that I actually used public transit; check your json data to see if this makes sense for you as well

ticket_time = 40 #validity time (in minutes) of one ticket within Vienna
#Assumes that trips shorter than this are "single-bout" trips, for which one ticket is sufficient

public_transport_list = ["IN_BUS","IN_SUBWAY","IN_TRAIN","IN_TRAM"] #list of public transit modes to be included


fpath = input("\nFile or folder path of Google data (press Enter to use default path as defined in the script):  ")
if fpath == "" :
    fpath = r"D:\Dropbox\Apps\Google Download Your Data\Location History\Semantic Location History\2023\Redacted" #example default path


import json
import re
from datetime import datetime
import sqlite3
import os
import urllib.request, urllib.parse, urllib.error
from urllib.request import urlopen


fpath = re.sub(r'^"|"$', '', fpath) #trim "" from beginning and/or end of file path if exists

if fpath.endswith('.json') : #a single json file selected
    full_path_list = [fpath] 
    
else :#a folder was selected - multiple files will be analyzed
    if not fpath.endswith('\\') :
        fpath = fpath + '\\' #always end with exactly one slash
    file_list = os.listdir(fpath) #list of all files within selected folder
    
    full_path_list = list()
    for fname in file_list : #get full path for each file in folder
        full_path_list.append(fpath + fname)
        
clean_path_list = list()
for fname in full_path_list : #only process redacted json files
    if fname.endswith('_redacted.json') : 
        clean_path_list.append(fname)

if clean_path_list == [] : #no relevant files selected
    print('No suitable files selected, program aborted\n\n**********************************')
    quit()

year = re.search(r'\\(\d{4})\\', fpath).group(1) #create path for SQL file to be created/modified
if len(clean_path_list) == 1 :
    sql_fpath = fpath[:-5] + '_SQL.sqlite'
    
else :
    sql_fpath = fpath + year + '_SQL.sqlite'
    
sql_file = sqlite3.connect(sql_fpath) #connect to SQL file 

cur = sql_file.cursor() #cursor of SQL file

#Create SQL tables. Main table is Journeys
cur.executescript('''
CREATE TABLE IF NOT EXISTS Journeys (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    StartTime SMALLDATETIME UNIQUE,
    EndTime SMALLDATETIME UNIQUE,
    StartCity_id INTEGER, EndCity_id INTEGER,
    activityGuess_id INTEGER, P_activity FLOAT,
    pubTransGuess_id INTEGER, P_transGuess FLOAT
);

CREATE TABLE IF NOT EXISTS ActivityTypes (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE, 
    Activity TEXT UNIQUE
);    
    
CREATE TABLE IF NOT EXISTS Locations (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
    City TEXT UNIQUE       
);

''')


#custom functions:
#-----------------


#nested function of get_prices(), used to confirm/determine ticket prices
def which_price(url, web_price, ticket_type) :

    if web_price is not None : #if price could be retrieved from website
    
        while True :
            which_price = input('\nPrice retrieved from website ( {} ) = {} Euros for {} ticket. Use this price? (Y/N)\t'.format(url, web_price, ticket_type))
            if which_price.lower() == 'y' :
                price = web_price                              
                break
            elif which_price.lower() == 'n' :
                while True :
                    set_price = input('Please set price for {} ticket (in Euros.cents):\t'.format(ticket_type))
                    try :
                        price = float(set_price)
                        break   
                    except: 
                        print('Please enter valid price (in Euros.cents)!')
                break
            
               
    else : #price retrieval unsuccessful 
    
        while True :
            set_price = input('\nPrice of {} ticket could not be retrieved from {}. Please set ticket price (in Euros.cents):\t'.format(ticket_type, url))
            try :
                price = float(set_price)
                break
            except: 
                print('Please enter valid price (in Euros.cents)!')
    
    print('Price of {} ticket set to: {} Euros.\n'.format(ticket_type, price))      
    
    return price
        

#fetch ticket prices from web (and compare to values defined in the beginning of this script)
def get_prices() :

    from bs4 import BeautifulSoup
    import ssl  
    
    # ignore ssl certificate errors
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    #web sources for ticket prices
    url_single = 'https://www.wien.info/de/reiseinfos/verkehr/tickets'
    url_yearly = 'https://www.wienerlinien.at/jahreskarte'
    '''Unfortunately I wasn't able to find one webpage that had info on both types of tickets. 
    If you come across such a web resource, please let me know!'''
    
    urls = (url_single, url_yearly) #tuple for loop    
    price_list = list() #for storing prices of different ticket types
    
    for ticket_type, url, text_to_find in zip(('single', 'yearly'), urls, ('Einzelticket', 'Euro pro Tag')) :
    
        try:         
            html = urlopen(url, context=ctx).read() #read and parse webpage
            soup = BeautifulSoup(html, "html.parser")            
            tags_with_price = soup.find_all(lambda tag: tag.name and text_to_find in tag.get_text())
            
            if ticket_type == 'single' : #relevant info is stored differently for each website / ticket type
                find_price = re.search(r'\b(\d+),(\d+)', tags_with_price[0].get_text()) #extract price in Euros and cents (separated by comma)
                Euros = find_price.group(1)
                cents = find_price.group(2)
                web_price = float(Euros + '.' + cents)    
                
            else : #for yearly ticket price
                per_day = re.search(r'(\d+)\s*Euro pro Tag', tags_with_price[0].get_text()).group(1) #price per day
                web_price = float(per_day) * 365 #price per year
                
            price = which_price(url, web_price, ticket_type)    

        except: 
            price = which_price(url, None, ticket_type)   
            
        price_list.append(price)
            
    print('\n')        
    return price_list
    
    
#load json data from redacted file
def load_json(file) :
    with open(file, 'r') as json_file: 
        data = json.load(json_file) #dict with 1 item ('timelineObjects')           
    return data
    

#use Dr. Chuck's geodata service to determine the city based on the redacted coords   
def get_city(coords, progress):
    
    #marks = ['\\', '|', '-', '/', '|'] #for showing progress    
    #print('Retrieving locations from geographic coordinates.... ' + marks[progress] + '\t', end='\r')
    
    serviceurl = r'http://py4e-data.dr-chuck.net/json?'
    api_key = 42 #non-unique API key used by this service
    
    url = serviceurl + urllib.parse.urlencode({'address': coords, 'key': api_key})
    #format url address
        
    u_h = urllib.request.urlopen(url) #url handle
    js_data = u_h.read().decode() #read json data from webpage
    data = json.loads(js_data) #data from json
    status = data['status'] #status of data retrieval
    results = data['results'] #results of geodata retrieval
    no_place = 'Unidentified' #value of unidentified locations
    
    if status != 'OK': 
        return no_place
    
    city, country = no_place, no_place #location not yet identified (default values)
    
    for result in results : #go through results list 
        if city != no_place and country != no_place : break 
        #if city and/or country are missing, keep looking; otherwise, leave for loop
        
        address = result['address_components'] #returns a list of address info
            
        for item in address :
            if 'locality' in item['types'] : #info regarding municipality
                city = item['long_name']
            elif 'airport' in item['types'] : #if this is an airport outside of a city, name the airport
                city = item['long_name'] 
            elif 'country' in item['types'] : #info regarding country
                country = item['long_name'] 
                
        if all(not c.isascii() or not c.isalpha() for c in city): #if all characters are non-ascii (e.g., Hebrew text), keep looking 
            city = no_place
        
        
    #to keep things in English
    if city == 'Wien' : city = 'Vienna'     
    
    location = city + ', ' + country #location name to be inserted into SQL
       
    return location
    
    
#check if public transit was used for this journey
def check_pub_trans(activity_type, activity_type_p, public_transport_list) :
    
    if activity_type in public_transport_list : #public transit use detected
    
        cur.execute('''INSERT OR IGNORE INTO ActivityTypes (Activity)
        VALUES ( ? )''', ( activity_type, )) #if does not yet exist, insert into ActivityTypes table
        
        cur.execute('SELECT id FROM ActivityTypes WHERE Activity = ? ', (activity_type, ))
        pub_trans_id = cur.fetchone()[0] #foregin key to be used by the main table
        
        p_pub_trans = activity_type_p #p of best guess of public transit use
        pub_stamp = True #mark that public transit use was detected
        
    else : #not a case of public transit use
        pub_stamp, pub_trans_id, p_pub_trans = False, None, None
                        
    return pub_stamp, pub_trans_id, p_pub_trans
                    

#get time from google json / SQL  
#Google json format: 2023-07-01T15:54:25.881Z (but len varies)
#SQL format: YYYY-MM-DD hh:mm:ss                  
def get_time(timestamp):

    if 'T' in timestamp : #google time format
        time = str(timestamp)[:10] + ' ' + str(timestamp)[11:19]
        #time format to insert into SQL
        
    elif len(timestamp) == 19 : #sql time format
        time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') 
        #time format for calculations based on data already in SQL
        
    else : 
        print('Timestamp could not be identified - check format of timestamp\n{}\n**********************************************'.format(timestamp))
        quit()
    return time
    
    
#populate SQL tables with data extracted from Google json data    
def fill_sql(data, cur, public_transport_list, new_journey_counter):

    progress = 0 #for showing progress during location extraction    
    
    for item in data : #go through list of dicts in json
        
        journey = item['activitySegment'] #dict holding all info on this journey
        
        #insert (unique) start and end times into main table
        start_time = journey['duration']['startTimestamp']
        end_time = journey['duration']['endTimestamp'] 
        
        start_sql = get_time(start_time)  
        end_sql = get_time(end_time)        
        
        cur.execute("SELECT StartTime FROM Journeys WHERE StartTime = ?", ( start_sql, ))
        existing_starttime = cur.fetchone() #check if this StartTime already exists
        
        if existing_starttime is not None : continue #if this journey already exists in the table, skip it
        else: 
            new_journey_counter += 1 #count how many new journeys were inserted to table 
            print('Retrieving locations from geographic coordinates - {} journeys added to table\t'.format(new_journey_counter), end='\r')
                            
        cur.execute('''INSERT INTO Journeys (StartTime, EndTime)
        VALUES ( ?, ? )''', ( start_sql, end_sql) ) 
        journey_id = cur.lastrowid #primary key of main table
                
        #get starting location of journey        
        start_latitude = journey['startLocation']['latitudeE7']
        start_longitude = journey['startLocation']['longitudeE7']
        start_coords = str(start_latitude) + ',' + str(start_longitude)
        start_city = get_city(start_coords, progress)
        
        cur.execute('''INSERT OR IGNORE INTO Locations (City)
        VALUES ( ? )''', ( start_city, ) )  
        cur.execute('SELECT id FROM Locations WHERE City = ? ', (start_city, ))
        start_city_id = cur.fetchone()[0] #foregin key to be used by the main table
                
        #get end location of journey
        end_latitude = journey['endLocation']['latitudeE7']
        end_longitude = journey['endLocation']['longitudeE7']
        end_coords = str(end_latitude) + ',' + str(end_longitude)
        end_city = get_city(end_coords, progress)   
                
        cur.execute('''INSERT OR IGNORE INTO Locations (City)
        VALUES ( ? )''', ( end_city, ) )         
        cur.execute('SELECT id FROM Locations WHERE City = ? ', (end_city, ))
        end_city_id = cur.fetchone()[0] #foregin key to be used by the main table
                
        #insert start and end locations to main table
        cur.execute('''UPDATE Journeys 
        SET StartCity_id = ?, EndCity_id = ?
        WHERE id = ?''', ( start_city_id, end_city_id, journey_id ))
        
        pub_stamp = False #default is that activity is not public transit use
        activity_id, pub_trans_id = None, None #values will be assigned only if use probabilities are suprathreshold
        activities = journey['activities'] #possible activities and transit modes
        p_activity = activities[0]['probability'] #P of best guess overall
        
        for a, activity in enumerate(activities) : #for each activity, get the best guess and also the best guess of public transit use (if suprathreshold)
            
            activity_type = activity['activityType'] #activity types and their probabilities (in %)
            activity_type_p = activity['probability']
            
            if activity_type_p < threshold_P : break 
            #if activity P subtreshold, we don't want it in the table
            #activities are arranged by P - if this P is too low then the next ones would be, too            
            
            if a == 0: #first guess is best guess of activity type overall
                cur.execute('''INSERT OR IGNORE INTO ActivityTypes (Activity)
                VALUES ( ? )''', ( activity_type, ))
                cur.execute('SELECT id FROM ActivityTypes WHERE Activity = ? ', (activity_type, ))
                activity_id = cur.fetchone()[0] #foregin key to be used by the main table
                    
                pub_stamp, pub_trans_id, p_pub_trans = check_pub_trans(activity_type, activity_type_p, public_transport_list)
                #check if this is a case of public transit use
                
                            
            else : #not the first guess
            
                if pub_stamp : break #if a case of public transport was already detected for this journey, don't keep looking
                                
                pub_stamp, pub_trans_id, p_pub_trans = check_pub_trans(activity_type, activity_type_p, public_transport_list)
                #check if this is a case of public transit use       
                    
        
        #insert activity guesses into main table (only if suprathreshold)
        if activity_id is not None :
            cur.execute('''UPDATE Journeys 
            SET activityGuess_id = ?, P_activity = ?
            WHERE id = ?''', ( activity_id, round(p_activity, 2), journey_id ))
        
        if pub_trans_id is not None : 
            cur.execute('''UPDATE Journeys 
            SET pubTransGuess_id = ?, P_transGuess = ?
            WHERE id = ?''', ( pub_trans_id, round(p_pub_trans, 2), journey_id ))
            
        progress += 1 #for progress bar
        if progress == 4: progress = 0
            
    return new_journey_counter #for counting how many new journeys entered into SQL file 

    
#use SQL data to detect unique public transit trips
def get_public_transit_sql(journey) :
    
    pub_trans_guess = journey[7] #guess regarding public transit use
    if pub_trans_guess is not None : #if public transit use guessed
        
        #trip must start and end in Vienna to be included in ticket price calculations
        start_city, end_city = journey[3], journey[4] 
        cur.execute('SELECT City FROM Locations WHERE id = ? ', ( start_city, ))
        city_name = cur.fetchone()[0] #actual name of city
        
        if end_city == start_city and city_name == 'Vienna, Austria': 
            trip_start = get_time(journey[1]) #start time of this journey
            return 1, trip_start #journey is a public transit trip within Vienna
    
    return 0, False #if journey does not contain public transit trip within Vienna
    
    
#go through the SQL data, extract info regarding unique public transit trips within Vienna
def read_sql(cur, ticket_time):
        
    cur.execute('SELECT * FROM Journeys ORDER BY StartTime')
    journeys = cur.fetchall() #returns list of journeys (each journey a tuple)
        
    #within the SQL data - when was the first journey, when was the last journey?
    very_first_journey = get_time(journeys[0][1])
    very_last_journey = get_time(journeys[-1][1])
    time_difference = very_last_journey - very_first_journey
    period_analyzed = time_difference.days + 1 #number of days included in analysis
  
    vienna_pubtrans_count = 0 #default value - no public transit use
    last_trip_start = None #default - there was no previous use of public transit in data
    
    for journey in journeys : #for each journey:
        counter, trip_start = get_public_transit_sql(journey) #check if this journey was a public transit trip within Vienna
        if trip_start : #identified a public transit trip within Vienna
            if last_trip_start is None : #this is the first Vienna public transit trip detected
                vienna_pubtrans_count += counter #add trip to count                
            else : #not first trip detected
                d_rides = round((trip_start - last_trip_start).total_seconds() / 60 )
                #what was the time difference (in minutes) between the start of both trips?

                if d_rides > ticket_time : #if time gap is sufficient, then this journey is not part of the previous one
                    vienna_pubtrans_count += counter #add trip to count
            
            last_trip_start = trip_start #update last trip start time to current trip start time

    return journeys, vienna_pubtrans_count, period_analyzed, very_first_journey, very_last_journey
    


#calculate and summarize whether yearly ticket is beneficial
def calculate_summarize(single_ticket_price, vienna_pubtrans_count, yearly_ticket_price, period_analyzed, very_first_journey, very_last_journey) :
    
    #calculations
    single_ticket_all_rides = single_ticket_price * vienna_pubtrans_count
    yearly_ticket_per_period = yearly_ticket_price * (period_analyzed / 365)
    d_ticket_prices = round(single_ticket_all_rides - yearly_ticket_per_period, 1)

    #output to user
    print('\nA total of {} public transit rides within Vienna detected for the period starting on {} and ending on {} ({} days).'.format(vienna_pubtrans_count, very_first_journey.date(), very_last_journey.date(), period_analyzed))        
    if d_ticket_prices > 0 :
        print('A yearly ticket would have saved {} Euros as compared to single-ride tickets for this time period.'.format(d_ticket_prices))
    else :
        print('No advantage of a yearly ticket for this time period.\nThe yearly ticket would have cost {} Euros more than single-ride tickets.'.format(-d_ticket_prices))
        
    return single_ticket_all_rides, yearly_ticket_per_period



#gather data from sql regarding the frequency of different kinds of activities     
def activities_over_time(journeys, cur, public_transport_list, very_first_journey, very_last_journey) :
    
    import calendar
    
    cur.execute('SELECT * FROM ActivityTypes')
    activities = cur.fetchall() #returns list of activities from sql (id, name)
    
    #dict and list for storing activity types
    activity_dict = dict()
    activity_list = list()
            
    for activity in activities : #for each activity type
        activity_id, activity_name = activity[0], activity[1] 
        if activity_name in public_transport_list : #we want all public transit types under one category
            activity_name = 'PUBLIC TRANSIT'
        if '_' in activity_name : #style adjustment
            activity_name = activity_name.replace('_',' ')
        activity_dict[activity_id] = activity_name #add dict item where activity_id points to activity_name
        if activity_name not in activity_list : #if activity name not already in list, add it
            activity_list.append(activity_name) 
    
    very_first_journey, very_last_journey = str(very_first_journey), str(very_last_journey)
    #used for deciding if No. of days in month need to be adjusted
    
    #dicts for counting 
    counts = dict() #count of activity types per month
    counts_per_day = dict() #count normalized as activity per day
    
    for journey in journeys : #go through all journeys in the Journeys table
        month = journey[1][5:7]
        year = journey[1][0:4]
        month_name = calendar.month_name[int(month)] + ' ' + year
        
        days_in_month = calendar.monthrange(int(year), int(month))[1] #number of days in this calendar month
        if very_first_journey[5:7] == month and very_first_journey[8:10] != '01' : 
            #if the first journey in the table was not on the first day of the month, adjust days in month
            first_day = int(very_first_journey[8:10])
            days_in_month = days_in_month - first_day + 1
        if very_last_journey[5:7] == month and int(very_last_journey[8:10]) != days_in_month :
            #if the last journey in the table was not on the last day of the month, adjust days in month
            days_in_month = int(very_last_journey[8:10])            
 
        if month_name not in counts.keys() : #fill the counts dictionary with subdictionaries
            counts[month_name] = dict()
            counts_per_day[month_name] = dict()
            counts[month_name]['Days'] = days_in_month
            for activity in activity_list :
                counts[month_name][activity] = 0 
                #for all months store the count of all activities, even if some counts = 0
            
        activity_id = journey[5] 
        if activity_id is not None : #only consider identified activity types
            activity = activity_dict[activity_id] #extract activity name
            counts[month_name][activity] += 1 #add 1 to count of this activity during this month
            #didn't use the get method since I also want values of 0 to be shown


    for month_name in counts.keys() : #for each activity type per month normalize the activity counts as counts per day        
        for activity in activity_list :
            counts_per_day[month_name][activity] = round(counts[month_name][activity] / counts[month_name]['Days'], 2)

    return counts, activity_list, counts_per_day
    
    
#visualize data    
def plot_data(single_ticket_all_rides, yearly_ticket_per_period, counts, activity_list, counts_per_day):

    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    import matplotlib.ticker as ticker
    
    #create a fig with 2 subplots
    plt.figure(1, figsize=(10, 5)) 
    grid = GridSpec(1, 2, width_ratios=[1, 3]) #subplot 2 is wider

    #show price difference in a bar graph
    price_values = [single_ticket_all_rides, yearly_ticket_per_period]
    bar_titles = ['Single Ride', 'Yearly Pass'] 

    #properties of price difference graph
    ax1 = plt.subplot(grid[0, 0])    
    ax1.bar(bar_titles, price_values, color=['cyan', 'magenta'])
    ax1.set_title('Price Difference')
    ax1.set_xlabel('Ticket Type')
    ax1.xaxis.set_major_locator(ticker.FixedLocator(range(len(bar_titles))))
    ax1.set_xticklabels(bar_titles, rotation=45)
    ax1.set_ylabel('Price per Period (Euros)')
    
    #show types of journeys over time in a line graph
    month_list = list(counts.keys()) #list for holding full month names (month, year)
    short_month_list = list() #list for holding short names for x axis of plot
    for month_name in month_list :
        short_month_list.append(month_name[:3])               
    
    #values and properties of journeys/time graph
    ax2 = plt.subplot(grid[0, 1])
    
    for activity in activity_list:
        activity_values = [counts_per_day[month_name][activity] for month_name in month_list]
        ax2.plot(short_month_list, activity_values, label=activity.capitalize())
        
    ax2.set_title('Journey Types')
    ax2.set_xlabel('Month')
    ax2.xaxis.set_major_locator(ticker.FixedLocator(range(len(short_month_list))))
    ax2.set_xticklabels(short_month_list, rotation=45)
    ax2.set_ylabel('Journeys per Day')
    ax2.legend(loc='upper left')

    #adjust and show figure
    plt.subplots_adjust(top=0.93, bottom=0.25, left=0.1, right=0.95, wspace=0.35)
    plt.show()
    


#main program
#------------
    
new_journey_counter = 0

#check ticket prices on the web and confirm with user 
single_ticket_price, yearly_ticket_price = get_prices()

for files in clean_path_list : #for all json data files
    data = load_json(files) #extract data from json file
    new_journey_counter = fill_sql(data, cur, public_transport_list, new_journey_counter) #fill sql tables
    

print("\t"*10, "\n{} new journey(s) inserted into the Journeys table of {}.".format(new_journey_counter, re.search(r'[^\\]+$', sql_fpath).group()))        
if new_journey_counter > 0 : #were additional journeys inserted into the SQL file?
    sql_file.commit() #commit new journeys to SQL file
    

journeys, vienna_pubtrans_count, period_analyzed, very_first_journey, very_last_journey = read_sql(cur, ticket_time) #determine number of public transit uses in Vienna

#calculations regarding ticket prices
single_ticket_all_rides, yearly_ticket_per_period = calculate_summarize(single_ticket_price, vienna_pubtrans_count, yearly_ticket_price, period_analyzed, very_first_journey, very_last_journey)

#gather data from sql regarding the frequency of different kinds of activities     
counts, activity_list, counts_per_day = activities_over_time(journeys, cur, public_transport_list, very_first_journey, very_last_journey)

sql_file.close() #close connection to SQL file

plots = input('\n\nPress any key to show related graphs.')
plot_data(single_ticket_all_rides, yearly_ticket_per_period, counts, activity_list, counts_per_day) #visualize data 






