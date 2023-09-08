'''
Roni Hogri, August 2023

This program is meant to redact sensitive info from the relevant json files provided by Google. 
It goes through the selected folder (or file) provided in Google's 'Semantic Location History', 
and creates new json files (ending with '_redacted.json') that will then be used for further analysis.
The redacted json files will only include data necessary to allow the main program to function.
'''

import json
import re
import time
import os

#user input:
fpath = input("File or folder path of Google data (press Enter if file path inserted in script):  ")


fpath = re.sub(r'^"|"$', '', fpath) #trim "" from beginning and/or end of file path if exists


if fpath == "" : #use default path
    fpath = r"D:\Dropbox\Apps\Google Download Your Data\Location History\Semantic Location History\2023" #example default path
       

if fpath.endswith('.json') : #if only one file selected (not folder)
    full_path_list = [fpath] 
    
    
else :#if folder is selected
    if not fpath.endswith('\\') :
        fpath = fpath + '\\' #always end with exactly one slash
    file_list = os.listdir(fpath) #create a list of files in folder
    full_path_list = list() #list for storing names of json files
    for fname in file_list : #go through folder            
        if fname.endswith('.json') : #only include json files in this list
            full_path_list.append(fpath + fname)

clean_path_list = list() #list of finals to actually be redacted by this program   
for fname in full_path_list : #avoid files that were previously redacted
    if fname.endswith('_redacted.json') :
        print('File already redacted : {}\n*************REDACTION SKIPPED******************\n'.format(fname))
    else :
        clean_path_list.append(fname)
        

if len(clean_path_list) < 1 : #no suitable files selected - end program
    print('---------No suitable files selected for redaction. No FILE CHANGED!--------')
    quit() 
    

#custom functions:
#-----------------

#retrieve data from original json file    
def load_data(file) : 

    with open(file, 'r', encoding='utf-8') as json_orig: 
        data = json.load(json_orig)
    return data
 

#create new json data, containing only the 'activitySegment' dicts which are relevant for the main program
def choose_relevant_dicts(data) : 

    new_data = list() #list to contain redacted data
    
    for dictionary in data['timelineObjects']: #for each dictionary contained in the main array
              
        for keys in dictionary : 

            if keys == 'activitySegment' :
                new_data.append(dictionary)
                
    return new_data
    
            
#remove sensitive information from json data
def redact_data(dictionary):

    redaction_list = ['transitPath', 'simplifiedRawPath', 'deviceTag', 'placeId'] #list of dicts to be redacted
        
    for key, value in dictionary.items(): #for each key, value pair in activitySegment dicts
    
        if key in redaction_list : #redact sensitive info
            dictionary[key] = 'REDACTED'
            
        elif 'E7' in key : #reduce resolutions of geo coordinates
            if len(str(value)) != 9 : #check that original coords have the correct length
                print('WARNING!! Coordinate value has wrong number of digits, check!!')
                time.sleep(5) #give time to pause program if warning is shown
            new_coord = value * 10**(-7) #create low-resolution coords 
            new_coord = round(new_coord, 2)
            dictionary[key] = new_coord #replace full coords with redacted coords
        
        
        if isinstance(value, dict): #if value is itself a dictionary, go deeper
            redact_data(value)  # recurse into nested dictionary        
            
        elif isinstance(value, list): #if value is itself a list, go deeper
            for items in value: #for each item in the list
                if isinstance(items, dict): #check if this item is itself a dict
                    redact_data(items)  # recurse into nested dictionary within list                    
                
    return dictionary #revised activity_segment to be stored in new json data file
    

#save new json file and create "Redacted" folder if necessary    
def save_file(data, orig_fname) :
    
    new_fname = re.sub(r'(?<=\\2023\\)(.*)(?=\.json)', r'Redacted\\\1_redacted', orig_fname)
    #name of new json file = name of old json file + '_redacted'; to be placed in new 'Redacted' folder
        
    redacted_folder = os.path.dirname(new_fname) #path of 'Redacted' folder
    if not os.path.exists(redacted_folder): #create 'Redacted' folder if doesn't exist
        os.makedirs(redacted_folder)
    
    with open(new_fname, 'w') as json_new: #write revised data into new json file
            json.dump(data, json_new, indent=4)
    print("Redacted file created : ", new_fname)


#main program
#------------

for files in clean_path_list : #for all relevant json files
    orig_data = load_data(files) #load data from original json files
    relevant_data = choose_relevant_dicts(orig_data) #screen relevant dicts
    
    redacted_data = list() #create redacted data version
    for activity_segment in relevant_data :    
        redacted_segment = redact_data(activity_segment)
        redacted_data.append(redacted_segment)
    
    save_file(redacted_data, files) #save to new json file
    
