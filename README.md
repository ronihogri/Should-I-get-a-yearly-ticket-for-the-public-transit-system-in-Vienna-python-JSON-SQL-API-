# Should I get the yearly pass (Jahreskarte) for the Viennese public transit system? 
An app to check whether, for a given traveler, it would be cheaper to buy a yearly pass (Jahreskarte) for the Viennese public transit system rather than paying for a single-ride each time. Uses Googles location history data (JSON files), python, REST API, and SQLite.  
Roni Hogri, August 2023. 
<br><br>
Updated January 2024:
- Imporved documentation within py files.
- Better handling of cases where user interrupts the filling of the SQLite file and continues at a later time point.
- Main program can handle both original Google location history as well as the redacted version produced by 'json_redact.py' (see below).
<br><br>

## Background
Many people in Vienna take advantage of the city’s excellent public transit system. For frequent travelers it is often advantageous to purchase a yearly pass (Jahreskarte) rather than paying for a single-ride ticket each time. However, many people use the public transit system only occasionally, making it difficult to decide whether purchasing the Jahreskarte would be cost-effective. To address this issue, I developed a procedure utilizing Googles location history data (JSON files), python, a REST API for reverse geocoding, and SQLite.   
<br><br>
## How it works
The python program ‘annual_ticket_calculation_from_google_data.py’ (henceforth: ‘main program’) extracts location history data collected from your cell phone by Google to an SQL database. This data is then used to determine whether a yearly pass would have been more cost-effective than purchasing single-ride tickets during the period in question.   
For the required python libraries, please see ['requirements.txt'](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/requirements.txt).
<br><br>
## Steps (see pictures and comments below)
1.	Connect to your Google account and download your location history from [https://takeout.google.com/](https://takeout.google.com/)
2.	Unzip the folders you want to analyze, under ‘Location History\ Semantic Location History’. It’s possible to select data from one year, or from multiple years. 
3.	Optional: If you would like to share your location history files with others, you have the possibility to remove sensitive and unnecessary data from your Google location history files. To do this, run [json_redact.py](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/src/json_redact.py). 
4.	Run the main python program [annual_ticket_calculation_from_google_data.py](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/src/annual_ticket_calculation_from_google_data.py) and follow the instructions you receive.
    
**Note:** If you prefer not to download your own location history data, and would like to test the main program works on my example data, **skip steps 1-3** and run the main program on the provided ‘2023_REDACTED’ folder. The ‘2023_REDACTED’ folder already contains an SQLite file containing the information extracted from the example JSON files (‘2023_REDACTED_SQL.sqlite’). If you want the main program to export the Google JSON data to a new SQLite file, please delete or rename this file.
<br><br>
### Step 1: Download location history from your Google account

  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/download%20location%20history.png) 
  
  1.1 Go to [https://takeout.google.com/](https://takeout.google.com/), select ‘Location History’, and then scroll down and click on ‘Next step’. 
    

  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/download%20location%20history2.png) 
  
  1.2 Choose your preferred transfer method (e.g., via email). Mark ‘Export once’, and set ‘File type & size’ according to your preferences. Then click on ‘Create export’.
<br><br>
### Step 2: Unzip your location history data

  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/unzip.png)  
  Example of zipped location history.

<br><br>
### Step 3 (recommended): Use the ‘json_redact.py’ program to trim JSON files obtained from Google and remove potentially sensitive information:
This step is highly recommended if you would like to share your location history with others. It would also make the main program run faster.
  
  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/json_redact.png) 
  
  Output of the ‘json_redact.py’ program, showing the paths of the newly created redacted location history JSON files.

<br><br>
### Step 4 (using the main python program):

  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/cmd_retrieving.png) 

  4.1 When you activate the main program, it will ask you to choose a JSON file or a directory containing JSON files to analyze. It will then ask you where to store the newly created SQLite file (or where to find one that was previously created). The program will then start retrieving information regarding the journeys contained in the JSON files. Using a [mock-version of the Google API provided by Dr. Charles Severance](http://py4e-data.dr-chuck.net/json?), the program will identify locations (city, country) based on the geographic coordinates stored in the JSON files. I chose to use this API since it doesn’t require each potential user to obtain their own Google API key. The process of retrieving locations might take some time, so progress is continually displayed. It is possible to restart the program multiple times (e.g., after downloading additional data) – unique journeys will be added to the SQL table as needed. Note that the provided ‘2023_REDACTED’ folder already contains a filled SQLite file (‘2023_REDACTED_SQL.sqlite’); to fill the SQL data yourself, please delete or rename this SQLite file.

<br><br>
  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/sql_tables.png) 

  4.2 Tables created in SQLite by running the main program on my example JSON files ('2023_REDACTED' folder). The main table is called ‘Journeys’ (shown on the right), and it consists of the following columns: 
- ‘StartTime’ and ‘EndTime’ refer to the beginning and end times of journeys, respectively; this is important for determining the duration of a journey and for deciding whether multiple journeys actually belong to the same trip for which one single-ride ticket would suffice (e.g., subway + tram). In addition, ‘StartTime’ is used as the primary key of this table (since no 2 journeys can start at the exact same time).
- ‘StartCity_id’ and ‘EndCity_id’ refer to the locations in which journeys began and ended, respectively; the main python program uses this information to decide whether public transit trips were within Vienna (otherwise, other types of tickets, with different prices, would be required).
- ‘activityGuess_id’ refers to Google’s best guess regarding the type of journey recorded (see ‘Activity’ table, on the left). Google’s level of confidence regarding this guess (as %) is shown under ‘P_activity’. ‘pubTransGuess_id’ and ‘P_transGuess’ refer to Google’s best guess involving public transit use for each journey and its confidence level, respectively. For both types of guesses (‘activityGuess_id’ and ‘pubTransGuess_id’), only journeys where the confidence level (‘P_activity’ and ‘P_transGuess’, respectively) was higher than the set threshold were included in the table. Threshold value can be adjusted in the python main program as required; I set it to 30%, since this seemed to work well in cases where the ground truth was available to me. Note that, depending on Google’s confidence in its guesses, the ‘activity_Guess_id’ is often, but not always, identical to the ‘pubTransGuess_id’ of a given journey - for example, see line 98 of the Journeys table. 
- 'Completed' shows the time at which each journey record (row) was completed; NULL indicates that this record is not yet fully populated (if the user previously interrupted the python program before all journey attributes could be exported to SQL). 

<br><br>
  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/cmd_summary.png) 
  
  4.3 Once all journeys in the selected JSON files have been stored in the SQLite file, the program reports how many new journeys were inserted into the SQLite file during the current run, and how many complete journey records exist in the SQLite file. Next, the prices for the different ticket types are retrieved from the web and displayed to be confirmed by the user. The program then provides a short summary of the information extracted from the existing SQLite file. Finally, the program reports whether a yearly ticket (Jahreskarte) would have been more cost-effective than using single-ride tickets for the selected period(s), and how much money would be saved by using the more cost-effective method. 

<br><br>
  ![](https://github.com/ronihogri/Vienna-yearly-ticket-calculator/blob/main/images/plots.png) 
  
  4.4 The program displays two graphs showing relevant information obtained from Google’s location history. Left: A comparison between single-ride and yearly pass tickets for the selected period. Right: The normalized frequency of different kinds of journeys during the selected period, to facilitate the identification of travel mode trends over time. 
