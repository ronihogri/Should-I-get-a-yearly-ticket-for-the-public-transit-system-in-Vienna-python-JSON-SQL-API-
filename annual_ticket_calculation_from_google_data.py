'''
Roni Hogri, August 2023

The purpose of this program is to use Google location data to calculate whether a yearly ticket (Jahreskarte) in Vienna would have been cheaper 
than buying single-ride tickets for the selected period. 
This program is meant to run on JSON location history data produced by Google. It can also work on redacted JSON data created by the json_redact.py program. 
For more details, see README. 

Note: For geodata processing, this program uses the website provided by Dr. Charles Severance, see:
http://py4e-data.dr-chuck.net/
This is a subset of data from the Google Geo Coding API - it does not require you to get a personal API key or pay any fees to Google.
'''


"""User-definable variables; modify according to individual preferences / knowledge if necessary:"""

threshold_P = 30.0 #threshold (in %) over which probability is high enough to be considered.
#I found that P > 30% of public transit use usually meant that I actually used public transit; check your json data to see if this makes sense for you as well.

ticket_time = 40.0 #validity time (in minutes) of one ticket within Vienna. 
#The program assumes that trips shorter than this value are "single-bout" trips, for which one ticket is sufficient.

public_transit_modes = ["IN_BUS","IN_SUBWAY","IN_TRAIN","IN_TRAM"] #list of public transit modes to be included

"""End of user-defined variables."""


#import libraries for global use:
import json
import re
from datetime import datetime
import sqlite3
import os
import sys
import urllib.request, urllib.parse, urllib.error
from urllib.request import urlopen

"""Globals:"""
new_journey_counter = 0 #counter for new journeys added to SQLite file during a particular run
sql_file = None #connection to SQL database


"""Functions:"""


def check_class(user_vars) :
    """Ensure that user-definable vars are of the right type; if not, try to enforce the correct classes, or quit if you can't.
    
    Args:
        user_vars (tuple): For each user-definable var, contains a dict with relevant info ('varname', 'value', and 'class').
        
    Returns:
        tuple: Values of (redefined) variables.
        
    Raises: 
        Terminates program if a user-definable var is of the wrong class and correct class cannot be enforced.        
    """
    
    user_var_list = list()
    for var in user_vars :
        if not isinstance(var['value'], var['class']) :
            try: 
                exec(f"var['value'] = {var['class'].__name__}(var['value'])")
                print(f"converted {var['varname']} to class {var['class'].__name__}.")   
            except:
                terminate(f"Variable '{var['varname']}' belongs to wrong class ({type(var['value']).__name__}); should be {var['class'].__name__}. Please redefine and try again. ", "")           
            
        user_var_list.append(var['value'])
        
    return tuple(user_var_list)



def terminate(m1='', m2='') :
    """Terminate program as required, and provide context for termination. Close SQL connection if open.
    
    Args:   
        m1, m2 (str): Messages providing the context for program termination.
        
    Globals: 
        sql_file (sqlite3.Connection): Connection to SQL database.
        
    Returns:
        None
    """
    
    sql_file.close()
    print(f'\n---------{m1}Program terminated{m2}--------\n')
    sys.exit()
    
    
    
def choose_file() :
    """Prompt the user to choose a file or folder containing the original or redacted Google JSON files. 
    
    Returns:    
        json_path_list (list): Path(s) of JSON file(s) to be analyzed.
        
    Raises:
        If no valid path is provided, asks the user to enter valid path or to quit the program.
    """
    
    fpath = input("\nInsert file or folder path of Google location history data (or press ENTER to use current dir):\t")    
    if fpath == "" :
        fpath = os.getcwd()
        
    while True : #keep going until valid path provided or user quits
    
        try : #if inputted path is invalid, prompt user to try again or quit
        
            fpath = re.sub(r'^"|"$', '', fpath) #trim "" from beginning and/or end of file path if exists
            
            if fpath.endswith('.json') : #if only one file selected (not folder)
                js
                on_path_list = [fpath] 
            else : #if folder is selected
                fpath = os.path.join(fpath, '')  #ensure that path ends with the system-appropriate path separator
                file_list = os.listdir(fpath)  #create a list of files in the folder
                json_path_list = [os.path.join(fpath, fname) for fname in file_list if fname.endswith('.json')]
                #create a list including only the json files in the folder
                                       
            if json_path_list == [] : #no suitable files selected
                fpath = input('\nNo suitable files selected for analysis. Please provide a valid path, or type "Q" + ENTER to quit.\t')   
                if fpath.strip().lower() == 'q' :
                    terminate(' ', ' by user. NO FILE ANALYZED!')                    
            else : break #break out of while loop
                   
        except : #user input invalid
            fpath = input('\nNo suitable files selected for analysis. Please provide a valid path, or type "Q" + ENTER to quit.\t')
            if fpath.strip().lower() == 'q' :
                terminate(' ', ' by user. NO FILE ANALYZED!') 
            else : continue
            
    return json_path_list
    


def sql_define(json_file_list) :
    """Create or fetch path of SQL file for data storage and extraction. Connect to SQLite file and get its handle. Create tables in SQL file if do not yet exist.
    
    Args: 
        json_file_list (list): JSON files to be analyzed.
        
    Globals:
        sql_file (sqlite3.Connection): Connection to SQL database. 
        
    Returns:
        sql_fpath (str): Path to SQL database.        
        cur (sqlite3.Cursor): Handle of SQL file.
        
    Raises:
        If SQLite file cannot be created/accessed in specific location, asks for alternative path or allows to terminate program.
    """
    
    global sql_file #for connecting to SQLite file
    
    sql_fpath = input('\nDefine path for SQLite file to contain the database used for this analysis, or press ENTER to use default path based on the JSON files selected:\t')
    
    while True : #keep going until valid path provided or user quits
    
        if sql_fpath == '' :
            sql_fpath = os.path.join(os.path.dirname(json_file_list[0]), os.path.basename(os.path.dirname(json_file_list[0])) + '_SQL.sqlite')
                   
        #Make sure SQL file extension is sqlite
        path_no_extension, extension = os.path.splitext(sql_fpath) 
        if extension != '.sqlite' :
            sql_fpath = path_no_extension + '.sqlite'
            
        if not os.path.exists(sql_fpath) :
            path_query = input(f'\nNew SQLite file will be created: {sql_fpath}\nType "Y" + ENTER to confirm, "Q" + ENTER to quit program, or insert new path to replace the file name or location:\t')              
        else :
            path_query = input(f'\nExisting SQLite file will be used: {sql_fpath}\nType "Y" + ENTER to confirm, "Q" + ENTER to quit program, or insert new path to replace the file name or location:\t')
                         
        if path_query.strip().lower() == 'y' :
            print('\n')
            try :
                sql_file = sqlite3.connect(sql_fpath) #create SQL file if not yet created, and connect to it
                cur = sql_file.cursor() #cursor of SQL file 
                break #break out of while loop
            except: 
                sql_fpath = input('''\nCould not access specified SQLite file, please check. 
Provide alternative path, press ENTER to use default path, or type "Q" + ENTER to quit the program:\t''')
                if sql_fpath.strip().lower == 'q' :
                    terminate('No valid SQLite file provided. ', '. SQL database was not altered')
        elif path_query.strip().lower() == 'q' :
            terminate('','')                                
        else: 
            sql_fpath = path_query
            continue #restart from while
                       

    #Create SQL tables if they don't yet exist - main table is Journeys:
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS Journeys (
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
        StartTime SMALLDATETIME UNIQUE,
        EndTime SMALLDATETIME UNIQUE,
        StartCity_id INTEGER, EndCity_id INTEGER,
        activityGuess_id INTEGER, P_activity FLOAT,
        pubTransGuess_id INTEGER, P_transGuess FLOAT,
        Complete INTEGER DEFAULT NULL
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
    
    return sql_fpath, cur



def load_json(file) :
    """Load JSON data from original/redacted Google location history file.
    
    Args: 
        file (str): Path of JSON file to get data from.
    
    Returns: 
        data (list): List of dicts from JSON data.
    """
    
    with open(file, 'r', encoding='utf-8') as json_file: 
        data = json.load(json_file) 
        
    try :
        data = data['timelineObjects'] #in case this is a non-redacted json file, get list of dicts from data
    except : pass    
    
    return data
    
    

def fill_sql(data, cur, public_transit_modes):
    """Populate SQL tables with data from Google JSON about journeys. Updates new_journey_counter globally.

    Args:
        data (dict): JSON data in dict form {'timelineObjects': []}.
        cur (sqlite3.Cursor): Handle of SQL file.
        public_transit_modes (list): List of public transit types for ticket price calculations.
        
    Globals:
        new_journey_counter (int): Counter of new entries to SQL database, continuously updated.

    Returns:
        None
    """
    
    global new_journey_counter #counter of entries to SQL database, continuously updated    
  
    for item in data : #go through list of journey dicts in json (1 journey per dict)
    
        if next(iter(item)) != 'activitySegment' : continue #only consider dicts with journey info for subsequent steps            
        
        journey = item['activitySegment'] #dict holding all info on this journey
        
        activities = journey['activities'] #possible activities (journey types)
        journey_id = activity_id = None #values will be assigned only if activity probabilities are suprathreshold

        for a, activity in enumerate(activities) : #for each activity, get the best guess and also the best guess of public transit use (if suprathreshold)
            
            activity_type = activity['activityType'] #activity type  
            activity_p = activity['probability'] #activity probabilities (Google's estimation, in %)                 
           
            if activity_p < threshold_P : break #if activity P subtreshold, we don't want it in the table - skip to next journey                
            #(activities are arranged in descending order of Ps - if this P is too low then the next ones would be, too)
                
            if a == 0 : #first guess, if suprathreshold, always goes into the Journeys table:
                #insert (unique) start and end times into main table:
                start_time = journey['duration']['startTimestamp']
                end_time = journey['duration']['endTimestamp'] 
                #convert time stamps to sql format:
                start_sql = get_time(start_time)  
                end_sql = get_time(end_time) 
                
                cur.execute('SELECT StartTime FROM Journeys WHERE StartTime = ? ', ( start_sql, ))
                existing_starttime = cur.fetchone() #check if this timestamp is already in the table
        
                if existing_starttime is not None: #is there already a journey with this timestamp in the table?
                    cur.execute('SELECT id FROM Journeys WHERE StartTime = ? AND Complete IS NULL', ( start_sql, ))
                    incomplete_row = cur.fetchone() #check if an incomplete journey record exists
                    if incomplete_row is None: break #journey already successfully inesrted into table, skip to next journey
                    else: #journey record incomplete
                        journey_id = incomplete_row[0] #id of the journey record to be completed                
                else : #no exiting journey, create a new one:
                    cur.execute('''INSERT INTO Journeys (StartTime, EndTime)
                    VALUES ( ?, ? )''', ( start_sql, end_sql) )  #insert new row
                    journey_id = cur.lastrowid #id of new row
                      
                #get starting location of journey and store in Locations table if not yet there:
                start_latitude = journey['startLocation']['latitudeE7']
                start_longitude = journey['startLocation']['longitudeE7']
                start_coords = str(start_latitude) + ',' + str(start_longitude)
                start_city = get_city(start_coords)
                
                cur.execute('''INSERT OR IGNORE INTO Locations (City)
                VALUES ( ? )''', ( start_city, ) )  
                cur.execute('SELECT id FROM Locations WHERE City = ? ', (start_city, ))
                start_city_id = cur.fetchone()[0] #foregin key to be used by the main table
                        
                #get end location of journey and store in Locations table if not yet there:
                end_latitude = journey['endLocation']['latitudeE7']
                end_longitude = journey['endLocation']['longitudeE7']
                end_coords = str(end_latitude) + ',' + str(end_longitude)
                end_city = get_city(end_coords)   
                        
                cur.execute('''INSERT OR IGNORE INTO Locations (City)
                VALUES ( ? )''', ( end_city, ) )         
                cur.execute('SELECT id FROM Locations WHERE City = ? ', (end_city, ))
                end_city_id = cur.fetchone()[0] #foregin key to be used by the main table
                        
                #insert start and end location ids to main table:
                cur.execute('''UPDATE Journeys 
                SET StartCity_id = ?, EndCity_id = ?
                WHERE id = ?''', ( start_city_id, end_city_id, journey_id ))       
                
                #insert activity_type into ActivitTypes table if not already there:
                cur.execute('''INSERT OR IGNORE INTO ActivityTypes (Activity)
                VALUES ( ? )''', ( activity_type, ))
                
                cur.execute('SELECT id FROM ActivityTypes WHERE Activity = ? ', (activity_type, ))
                activity_id = cur.fetchone()[0] #activity id to be used by the main table
                        
                #insert first activity guess into main table:            
                cur.execute('''UPDATE Journeys 
                SET activityGuess_id = ?, P_activity = ?
                WHERE id = ?''', ( activity_id, round(activity_p, 2), journey_id ))     

                if activity_type in public_transit_modes : #public transit use detected for this journey
                    #insert public transit guess into main table:            
                    cur.execute('''UPDATE Journeys 
                    SET pubTransGuess_id = ?, P_transGuess = ?
                    WHERE id = ?''', ( activity_id, round(activity_p, 2), journey_id ))                      
                    break #public transit use was already detected for this journey, skip to next journey                
                            
            else : #suprathreshold but not the first guess - in this case we're only intersted in public transit journeys               
                
                if activity_type in public_transit_modes : #public transit journey?
                    
                    #insert suprathreshold public transit activity_type into ActivitTypes table if not already there:
                    cur.execute('''INSERT OR IGNORE INTO ActivityTypes (Activity)
                    VALUES ( ? )''', ( activity_type, ))
                    
                    cur.execute('SELECT id FROM ActivityTypes WHERE Activity = ? ', (activity_type, ))
                    activity_id = cur.fetchone()[0] #public transit id to be used by the main table
                                    
                    #insert public transit info into main table:
                    cur.execute('''UPDATE Journeys 
                    SET pubTransGuess_id = ?, P_transGuess = ?
                    WHERE id = ?''', ( activity_id, round(activity_p, 2), journey_id ))
                    
        if journey_id is not None: #journey record successfully completed
            cur.execute('''UPDATE Journeys
            SET Complete = 1
            WHERE id = ?''', ( journey_id, )) #mark that the filling of this row has been completed 
    
            new_journey_counter += 1 #count how many journeys were successfully updated in the table in this run
            print(f'Retrieving locations from geographic coordinates - {new_journey_counter} journeys added to table. Press Ctrl+C to interrupt. \t', end='\r')               
    
    
                    
def get_time(timestamp):
    """Get time from JSON / SQL, and output the timestamp in the necessary format. 
        
    Google JSON format example: 2023-07-01T15:54:25.881Z (len varies).
    SQL format: YYYY-MM-DD hh:mm:ss  .
    
    Args: 
        timestamp (str): Timestamp extracted from JSON or SQL file.
    
    Returns: 
        new_timestamp (str): Reformatted timestamp. 
    """

    if 'T' in timestamp : #google time format
        new_timestamp = str(timestamp)[:10] + ' ' + str(timestamp)[11:19]
        #time format to insert into SQL
        
    elif len(timestamp) == 19 : #sql time format
        new_timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') 
        #time format for calculations based on data already in SQL
        
    else : 
        terminate(f'Timestamp "{timestamp}" could not be identified - check timestamp format. ', '')        
        
    return new_timestamp
    
    

def get_city(coords):
    """Determine the city in which a journey began/ended, based on geodata coords (by using Dr. Chuck's geodata service).
    
    Args: 
        coords (str): Geographic coordinates (Latitude, longitude). 
    
    Returns: 
        Location (str): Location corresponding to geodata coords, usually (city, country).
    """
        
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
    
    city = country = no_place #location not yet identified (default values)
    
    for result in results : #go through results list 
        if city != no_place and country != no_place : break 
        #if city and/or country are missing, keep looking; otherwise, exit loop
        
        address = result['address_components'] #returns a list of address info
            
        for item in address :
            if 'locality' in item['types'] : #info regarding municipality
                city = item['long_name']
            elif 'airport' in item['types'] : #if this is an airport outside of a city, name the airport
                city = item['long_name'] 
            elif 'country' in item['types'] : #info regarding country
                country = item['long_name'] 
                
        if all(not c.isascii() or not c.isalpha() for c in city): #if all characters are non-ascii (e.g., Hebrew text), keep looking 
            city = no_place #mark as unidentified for now
        
        
    #to keep things in English
    if city == 'Wien' : city = 'Vienna'     
    
    location = city + ', ' + country #location name to be inserted into SQL
       
    return location
   
   
    
def total_journey_count(cur) :
    """Report current number of valid instances (journeys) in the Journey table of the SQL file.
    
    Args:
        cur (sqlite3.Cursor): Handle of SQL file.
        
    Returns:
        count (int): Number of complete rows in Journeys table.
    """
    
    cur.execute('SELECT COUNT(*) FROM Journeys WHERE Complete = 1') #for reporting total number of journeys in DB
    count = cur.fetchone()
    if count is None : 
        count = 0
    else:
        count = count[0]
    return count
    


def read_sql(cur, ticket_time):
    """Go through the SQL database, extract info regarding unique public transit trips within Vienna.

    Args:
        cur (sqlite3.Cursor): Handle of the SQL file.
        ticket_time (float): Maximal duration (minutes) of a "single-bout" trip, for which one ticket is sufficient (user-definable var).

    Returns:
        A tuple containing the following elements:
            - journeys (list): List of journeys fetched from the SQLite file, each represented as a tuple.            
            - very_first_journey (datetime): Date and time of the very first journey in SQLite file.
            - very_last_journey (datetime): Date and time of the very last journey in SQLite file.
            - period_analyzed (int): Number of days included in the analysis.
            - vienna_pubtrans_count (int): Count of unique public transit trips within Vienna.
    """
        
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
                
        counter, trip_start = get_public_transit_sql(cur, journey) #check if this journey was a public transit trip within Vienna
        if trip_start : #identified a public transit trip within Vienna
            if last_trip_start is None : #this is the first Vienna public transit trip detected
                vienna_pubtrans_count += counter #add trip to count                
            else : #not first trip detected
                d_rides = round((trip_start - last_trip_start).total_seconds() / 60 )
                #what was the time difference (in minutes) between the start of both trips?

                if d_rides > ticket_time : #if time gap is sufficient, then this journey is not part of the previous one
                    vienna_pubtrans_count += counter #add trip to count
            
            last_trip_start = trip_start #update last trip start time to current trip start time

    return journeys, very_first_journey, very_last_journey, period_analyzed, vienna_pubtrans_count
    
    
    
def get_public_transit_sql(cur, journey) :
    """Use SQL data to detect unique public transit trips.
    
    Args:
        cur (sqlite3.Cursor): Handle of the SQL file.
        journey (tuple): A journey entry in the SQL database, where:
            - journey[7] (int): Guess regarding public transit use.
            - journey[3] (int): Start city ID.
            - journey[4] (int): End city ID.
            - journey[1] (str): Start timestamp.

    Returns:
        A tuple containing two elements:
            - int: The count of public transit trips detected within Vienna.
            - One of two options:
                -- datetime: the start time of the public transit trip (if detected).
                -- None: if no public transit trip within Vienna is found.
    """
    
    pub_trans_guess = journey[7] #guess regarding public transit use
    if pub_trans_guess is not None : #if public transit use guessed
        
        #trip must start and end in Vienna to be included in ticket price calculations
        start_city, end_city = journey[3], journey[4] 
        cur.execute('SELECT City FROM Locations WHERE id = ? ', ( start_city, ))
        city_name = cur.fetchone()[0] #actual name of city
        
        if end_city == start_city and city_name == 'Vienna, Austria': 
            trip_start = get_time(journey[1]) #start time of this journey
            return 1, trip_start #journey is a public transit trip within Vienna
    
    return 0, None #in case journey does not contain public transit trip within Vienna
    
    
    
def get_prices() :
    """Fetch ticket prices from web.
    
    Returns: 
        prices (tuple): Prices of (single, yearly) tickets.
    
    Raises:
        If price cannot be found online, web_price is replaced by None when calling which_price().
    """

    from bs4 import BeautifulSoup
    import ssl  
    
    # ignore ssl certificate errors
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    #web sources for ticket prices
    url_single = 'https://www.wien.info/de/reiseinfos/verkehr/tickets-361374'
    url_yearly = 'https://www.wienerlinien.at/jahreskarte'
    '''Unfortunately I wasn't able to find one webpage that had info on both types of tickets. 
    If you come across such a web resource, please let me know!'''
    
    #tuples for loop:
    ticket_types = ('single', 'yearly') 
    urls = (url_single, url_yearly)  
    prices = [] #list for prices, later converted to tuple
    
    for ticket_type, url, text_to_find in zip(ticket_types, urls, ('Einzelticket', 'Euro pro Tag')) :
    
        try: #try to get ticket price from web source        
            html = urlopen(url, context=ctx).read() #read and parse webpage
            soup = BeautifulSoup(html, "html.parser")            
            tags_with_price = soup.find_all(lambda tag: tag.name and text_to_find in tag.get_text()) #target text should be within a named tag            
            
            if ticket_type == 'single' : #relevant info is stored differently for each website / ticket type
                find_price = re.search(r'\b(\d+),(\d+)', tags_with_price[0].get_text()) #extract price in Euros and cents (separated by comma)
                Euros = find_price.group(1)
                cents = find_price.group(2)
                web_price = float(Euros + '.' + cents)    
                
            else : #for yearly ticket price
                per_day = re.search(r'(\d+)\s*Euro pro Tag', tags_with_price[0].get_text()).group(1) #price per day
                web_price = float(per_day) * 365 #price per year (same price for leap year...)
                
            price = which_price(url, web_price, ticket_type) 

        except KeyboardInterrupt: #in case user quits, don't ask for input on ticket price
            terminate('',' by  user')  
            
        except: #if price could not be retrieved from website, ask user to provide price
            price = which_price(url, None, ticket_type)           
            
        prices.append(price)
        
    return tuple(prices) #tuple to be used later on with other tuples
    
    
    
def which_price(url, web_price, ticket_type) :
    """Nested function of get_prices(), used to confirm/determine ticket prices.
    
    Args:
        url (str): URL from which the price should be obtained.
        web_price (float / None): Ticket price, according to website; or None if price could not be found online by get_prices().
        ticket_type (str): Ticket type (single-ride or yearly). 
    
    Returns: 
        Price (float): Ticket price to be used for analysis.     
        
    Raises:
        If type of price inputted by user not float, asks user to provide the correct price format.
    """    
    
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
    
    print('Price of {} ticket set to: {} Euros.\n\n'.format(ticket_type, price))      
    
    return price
    
    
    
def calculate_summarize(single_ticket_price, vienna_pubtrans_count, yearly_ticket_price, period_analyzed, very_first_journey, very_last_journey) :
    """Calculate and summarize whether yearly ticket would have been cost-effective.
    
    Args:
        single_ticket_price (float): Cost of single-ride ticket.
        vienna_pubtrans_count (int): Number of public transit trips within Vienna. 
        yearly_ticket_price (float): Cost of yearly ticket. 
        period_analyzed (int): Number of days in analyzed period. 
        very_first_journey (datetime): Date and time of the very first journey in SQLite file.
        very_last_journey (datetime): Date and time of the very last journey in SQLite file.
        
    Returns:
        A tuple containing two elements:
            - single_ticket_all_rides (float): Total cost of using a single-ride ticket for all rides included in analysis. 
            - yearly_ticket_per_period (float): Cost of using a yearly ticket, adjusted for the analyzed period. 
    """
    
    #calculations:
    single_ticket_all_rides = single_ticket_price * vienna_pubtrans_count
    yearly_ticket_per_period = yearly_ticket_price * (period_analyzed / 365)
    d_ticket_prices = round(single_ticket_all_rides - yearly_ticket_per_period, 1)

    #output to user:
    print('\nA total of {} public transit rides within Vienna detected for the period starting on {} and ending on {} ({} days).'.format(vienna_pubtrans_count, very_first_journey.date(), very_last_journey.date(), period_analyzed))        
    if d_ticket_prices > 0 :
        print('A yearly ticket would have saved {} Euros as compared to single-ride tickets for this time period.'.format(d_ticket_prices))
    else :
        print('No advantage of a yearly ticket for this time period.\nThe yearly ticket would have cost {} Euros more than single-ride tickets.'.format(-d_ticket_prices))
        
    return single_ticket_all_rides, yearly_ticket_per_period
    


def activities_over_time(cur, journeys, public_transit_modes, very_first_journey, very_last_journey) :
    """Gather data from sql regarding the frequency of different kinds of activities. 
    
    Args:
        cur (sqlite3.Cursor): Handle of SQL file.
        journeys (list): List of journeys fetched from the SQLite file, each represented as a tuple. 
        public_transit_modes (list): List of public transit types for ticket price calculations.
        very_first_journey (datetime): Date and time of the very first journey in SQLite file.
        very_last_journey (datetime): Date and time of the very last journey in SQLite file.
        
    Returns:
        A tuple containing the following elements:
            - activity_list (list): Types of journeys contained in the SQLite file. 
            - counts (dict): For each month, contains:
                -- The count for each type of journey. 
                -- The number of days to be considered. 
            - counts_per_day (dict): For each month, contains the count for each type of journey, normalized per number of days.         
    """
    
    import calendar #for retrieving month names and number of days per month
    
    cur.execute('SELECT * FROM ActivityTypes')
    activities = cur.fetchall() #returns list of activities from sql (id, name)
    
    #dict and list for storing activity types
    activity_dict = dict()
    activity_list = list()
            
    for activity in activities : #for each activity type
        activity_id, activity_name = activity[0], activity[1] 
        if activity_name in public_transit_modes : #we want all public transit types under one category
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

    return activity_list, counts, counts_per_day
    
    
    
def plot_data(single_ticket_all_rides, yearly_ticket_per_period, activity_list, counts, counts_per_day):
    """Visualize data.
    
    Args:
        single_ticket_all_rides (float): Total cost of using a single-ride ticket for all rides included in analysis. 
        yearly_ticket_per_period (float): Cost of using a yearly ticket, adjusted for the analyzed period.
        activity_list (list): Types of journeys contained in the SQLite file.        
        counts (dict): For each month, contains:
            - The count for each type of journey. 
            - The number of days to be considered.
        counts_per_day (dict): For each month, contains the count for each type of journey, normalized per number of days.                 
        
    Returns:
        None  
    """

    #import libraries for plotting:
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    import matplotlib.ticker as ticker
    
    #create a fig with 2 subplots:
    plt.figure(1, figsize=(10, 5)) 
    grid = GridSpec(1, 2, width_ratios=[1, 3]) #subplot 2 is wider

    #show price difference in a bar graph:
    price_values = [single_ticket_all_rides, yearly_ticket_per_period]
    bar_titles = ['Single Ride', 'Yearly Pass'] 

    #properties of price difference graph:
    ax1 = plt.subplot(grid[0, 0])    
    ax1.bar(bar_titles, price_values, color=['cyan', 'magenta'])
    ax1.set_title('Price Difference')
    ax1.set_xlabel('Ticket Type')
    ax1.xaxis.set_major_locator(ticker.FixedLocator(range(len(bar_titles))))
    ax1.set_xticklabels(bar_titles, rotation=45)
    ax1.set_ylabel('Price per Period (Euros)')
    
    #show types of journeys over time in a line graph:
    month_list = list(counts.keys()) #list for holding full month names (month, year)
    short_month_list = list() #list for holding short names for x axis of plot
    for month_name in month_list :
        short_month_list.append(month_name[:3])               
    
    #values and properties of journeys/time graph:
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

    #adjust and show figure:
    plt.subplots_adjust(top=0.93, bottom=0.25, left=0.1, right=0.95, wspace=0.35)
    plt.show()
  


def main() :
    """Main program for assessing whether a yearly pass or single-ride tickets would have been more cost-effective for a certrain period based on Google location history data.
    
    The program is suitable for analyzing the original JSON files produced by Google, or the redacted versions created by 'json_redact.py' (see README)."""
    
    global threshold_P, ticket_time, public_transit_modes
    user_vars=({'varname': 'threshold_P', 'value': threshold_P, 'class': float}, {'varname': 'ticket_time', 'value': ticket_time, 'class': float}, 
    {'varname': 'public_transit_modes', 'value': public_transit_modes, 'class': list}) #info on user-definable variables
    threshold_P, ticket_time, public_transit_modes = check_class(user_vars) #check that user-definable vars are of the right type, try to correct if not
    
    try :        
        json_file_list = choose_file() #prompt user to choose json file(s) to be included in the analysis
        sql_fpath, cur = sql_define(json_file_list) #defines the SQL database to be used
               
        for file in json_file_list : #for each json data file
            data = load_json(file) #extract data from json file
            try :
                fill_sql(data, cur, public_transit_modes) #fill sql tables
            except KeyboardInterrupt :
                if new_journey_counter > 0 :
                    sql_file.commit()                    
                print(f"{new_journey_counter} new journey(s) successfully inserted into the Journeys table of {sql_fpath}.\t\t\t\n")  
                print(f"The Journeys table now contains a total of {total_journey_count(cur)} valid journeys.\n")
                terminate('Exporting to SQL interrupted. ', ' by user')
        if new_journey_counter > 0 :
            sql_file.commit()   
        print(f"{new_journey_counter} new journey(s) successfully inserted into the Journeys table of {sql_fpath}.\t\t\t\n")  
        print(f"The Journeys table now contains a total of {total_journey_count(cur)} valid journeys.\n")
        
        journeys, very_first_journey, very_last_journey, period_analyzed, vienna_pubtrans_count = read_sql(cur, ticket_time) 
        #determine number of public transit uses in Vienna
                
        single_ticket_price, yearly_ticket_price = get_prices() #check ticket prices on the web and confirm with user
        
        single_ticket_all_rides, yearly_ticket_per_period = calculate_summarize(single_ticket_price, vienna_pubtrans_count,
        yearly_ticket_price, period_analyzed, very_first_journey, very_last_journey) #calculate costs of ticket options
        
        #print(single_ticket_all_rides, yearly_ticket_per_period)

        activity_list, counts, counts_per_day = activities_over_time(cur, journeys, public_transit_modes, 
        very_first_journey, very_last_journey)  #gather data from sql regarding the frequency of different kinds of activities 

        sql_file.close() #close connection to SQL file

        plots = input('\n\nPress any key to show related graphs.')
        plot_data(single_ticket_all_rides, yearly_ticket_per_period, activity_list, counts, counts_per_day) #visualize data 
    
    
    except KeyboardInterrupt :
        terminate('', ' by user')
        
    except Exception as e:
        terminate(f'An error occurred: {e}.\t', '')
    
    

"""Run program:"""
if __name__ == "__main__": 
    main() 
    




