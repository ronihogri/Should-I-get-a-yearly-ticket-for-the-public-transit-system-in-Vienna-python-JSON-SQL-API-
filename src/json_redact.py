'''
Roni Hogri, August 2023

This program is meant to redact sensitive info from the relevant json files provided by Google. 
It goes through the selected folder (or file) provided in Google's 'Semantic Location History', 
and creates new json files (ending with '_redacted.json') that can then be used for further analysis.
The redacted json files will only include data necessary to allow the main program ('annual_ticket_calculation_from_google_data.py') to function.
'''

#import libraries for global use:
import json
import re
import time
import os
import sys


"""Functions:"""


def choose_file() :
    """Ask the user to choose a file or folder containing the original Google json files to be redacted. 
    If no valid path is provided, ask the user to enter valid path or to quit the program.
    
    Returns: 
        clean_path_list (list) - path(s) of JSON file(s) to be redacted.
    """
    
    fpath = input("File or folder path of Google location history data:  ") #get location of original Google json files
    
    while True : #keep going until valid path provided or user quits
    
        try : #if inputted path is invalid, prompt user to try again or quit
        
            fpath = re.sub(r'^"|"$', '', fpath) #trim "" from beginning and/or end of file path if exists
            
            if fpath.endswith('.json') : #if only one file selected (not folder)
                full_path_list = [fpath] 
            else : #if folder is selected
                fpath = os.path.join(fpath, '')  #ensure that path ends with the system-appropriate path separator
                file_list = os.listdir(fpath)  #create a list of files in the folder
                full_path_list = [os.path.join(fpath, fname) for fname in file_list if fname.endswith('.json')]
                #create a list including only the json files in the folder
                
            clean_path_list = list() #list of files to actually be redacted by this program   
            for fname in full_path_list : #avoid files that were previously redacted
                if fname.endswith('_redacted.json') :
                    print('File already redacted : {}\n*************REDACTION SKIPPED******************\n'.format(fname))
                else :
                    clean_path_list.append(fname) 
                
            if clean_path_list == [] : #no suitable files selected
                fpath = input('No suitable files selected for redaction. Please provide a valid path, or type "Q" + ENTER to quit.\t')
                if fpath.strip().lower() == 'q' :
                    print('---------Program terminated by user. NO FILE CHANGED!--------')
                    sys.exit()       
            else : break #break out of while loop
                   
        except : #user input invalid
            fpath = input('No suitable files selected for redaction. Please provide a valid path, or type "Q" + ENTER to quit.\t')
            if fpath.strip().lower() == 'q' :
                print('---------Program terminated by user. NO FILE CHANGED!--------')
                sys.exit()
            else : continue
            
    return clean_path_list
    
    
    
def load_data(file) : 
    """Retrieve data from original json file.
    
    Args: 
        file (str) - file from file list.
    
    Returns: 
        data (dict) - extracted json data in dict form.
    """        
    
    with open(file, 'r', encoding='utf-8') as json_orig: 
        data = json.load(json_orig)
    return data
 
 
 
def choose_relevant_dicts(data) : 
    """Create new json data, containing only the 'activitySegment' dicts which are relevant for the main program.
    
    Args: 
        data (dict) - data from original json file.
    
    Returns: 
        A list containing dicts that are relevant for the main app. 
    """
        
    return [dictionary for dictionary in data['timelineObjects'] if 'activitySegment' in dictionary]
    
    
    
def redact_data(activity_segment) :
    """Remove sensitive information from json data.
    
    Args: 
        activity_segment (dict) - original data from relevant sections of the json file. 
    
    Returns: 
        activity_segment (dict) - redacted data, with potentially sensitive data removed.
    """

    redaction_list = ['transitPath', 'simplifiedRawPath', 'deviceTag', 'placeId'] #list of dicts to be redacted
        
    for key, value in activity_segment.items() : #for each key, value pair in activitySegment dicts
    
        if key in redaction_list : #if this field contains sensitive info, redact it
            activity_segment[key] = 'REDACTED'
            
        elif 'E7' in key : #reduce resolutions of geo coordinates (to 2 digits after the decimal)
            value_len = len(str(value))
            activity_segment[key] = round(value * 10**( -(value_len - 2)), 2) # store low-resolution coords 
        
        if isinstance(value, dict) : #if value is itself a dictionary, go deeper
            redact_data(value)  # recurse into nested dictionary        
            
        elif isinstance(value, list) : #if value is itself a list, go deeper
            for item in value: #for each item in the list
                if isinstance(item, dict) : #check if this item is itself a dict
                    redact_data(item)  # recurse into nested dictionary within list                    
                
    return activity_segment #revised activity_segment to be stored in new json data file
    

def save_file(data, orig_fpath, flag=False) :
    """Save new json file(s) in '_REDACTED' folder in the same directory as the original folder. 
    
    Args:
        data (list) - redacted json data.
        orig_fpath (str) - path of original (non-redacted) json file from Google.
        flag (bool) - False by default; set to True if there are problems saving the new file.
        
    Returns:
        bool: Returns True if new file could be successfully saved.
        
    Raises: 
        If file can't be saved in intended location, gives the user an option to designate a new location or quit the program. 
    """
    
    if not flag :
        orig_dir, orig_filename = os.path.split(orig_fpath) #extract the directory and filename from the original path
        redacted_folder = os.path.join(os.path.dirname(orig_dir), os.path.basename(orig_dir) + '_REDACTED') #create the new directory path for the '_REDACTED' folder
        fname_no_extension, _ = os.path.splitext(orig_filename)
        new_filename = f'{fname_no_extension}_redacted.json' #create the new filename for the redacted file
        new_fpath = os.path.join(redacted_folder, new_filename) #create the full path for the redacted file
           
    try :
        if not os.path.exists(redacted_folder) :  #create '_REDACTED' folder if it doesn't exist
            os.makedirs(redacted_folder)

        with open(new_fpath, 'w') as json_new :  #write revised data into new json file
            json.dump(data, json_new, indent=4)
        print("Redacted file created:", new_fpath)

    except Exception as e :
        new_fpath = input(f'Error encountered: {e}\nCould not save file in intended location: {new_fpath}\nPlease provide an alternative path for the redacted file, or type "Q" + ENTER to quit:\t')
        if new_fpath.strip().lower() == 'q' :
            print('---------Program terminated by user--------')
            sys.exit() #terminate program
        save_file(data, new_fpath, flag=True) #try saving the file to the new path provided by user
        
    return True
    
   

  
def main() : 
    """Main program for redacting JSON files containing Google location history data. 
    
    This program should be used if you want to share location history with others but want to protect sensitive info."""
    
    file_list = choose_file() #prompt user to choose file(s) to be redacted
    redaction_count = 0 #counter for the number of redacted JSON files created in this run
    
    for file in file_list : #for all relevant json files
        orig_data = load_data(file) #load data from json file as dict
        relevant_data = choose_relevant_dicts(orig_data) #create list containing only dicts that contain data relevant for the main app
            
        redacted_data = list() #create list of dicts holding redacted data
        for activity_segment in relevant_data : #for each activitySegment dict  
            redacted_segment = redact_data(activity_segment) #create redacted dict
            redacted_data.append(redacted_segment) #add to list of redacted data
            
        if save_file(redacted_data, file): #save to new json file  
            redaction_count += 1
    print(f'\nTotal of {redaction_count} new redacted files successfully created.')
     
     

"""Run program:"""
if __name__ == "__main__": 
    main()