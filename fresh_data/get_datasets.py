
import re
import math
import requests
import geopandas
import numpy as np
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from fuzzywuzzy import process
from fuzzymatcher import link_table, fuzzy_left_join

state_mapping = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AS": "American Samoa",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District Of Columbia",
    "FM": "Federated States Of Micronesia",
    "FL": "Florida",
    "GA": "Georgia",
    "GU": "Guam",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MH": "Marshall Islands",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "MP": "Northern Mariana Islands",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PW": "Palau",
    "PA": "Pennsylvania",
    "PR": "Puerto Rico",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VI": "Virgin Islands",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming"
}

cast_code_mapping = {
    "0" : "Not a member of the chamber when this vote was taken",
    "1" : "Yea",
    "2" : "Paired Yea",
    "3" : "Announced Yea",
    "4" : "Announced Nay",
    "5" : "Paired Nay",
    "6" : "Nay",
    "7" : "Present (some Congresses)",
    "8" : "Present (some Congresses)",
    "9" : "Not Voting (Abstention)"
}

def string_to_percent(str_percent):
    str_num = re.sub("[%< ]", '', str_percent)
    if len(str_num) == 1:
        str_num = "0"+str_num
    return float("0."+str_num)

def get_age(x):
    born = x["born"]
    died = x["died"]
    year_start = int(x["year_range"][:4])
    if not pd.isna(died):
        age = died - born
    else:
        age = year_start - born
    return age

def get_parties():# get a unique mapping of all parties the US has ever had registered:
    parties_df = pd.read_csv("fresh_data/HSall_parties.csv")
    parties_df = parties_df.groupby(['party_code','party_name'])["n_members"].sum().reset_index().rename(columns={'n_members':'count_all_time'})
    return {party_code:parties_df[parties_df["party_code"] == party_code]["party_name"].item() for party_code in parties_df["party_code"].unique()}

def get_populations(root):
    total_population_df = pd.read_excel(root+"/population-change-data-table.xlsx", skiprows=4).rename({"Unnamed: 0": "Area"}, axis=1)
    total_population_df.head()

    total_population_1970_2020 = total_population_df.loc[:,["Area"]]

    for year in [2020, 2010, 2000, 1990, 1980, 1970]:
        total_population_1970_2020.loc[:, f"{year}"] = total_population_df.loc[:,f"Resident Population {year} Census"]

    return total_population_1970_2020

def get_religions_and_geography():
    # Get religious composition of states as well as geographic data

    # Scrape the PEW Research Center for their statistics on the current religous landscape:
    url = "https://www.pewresearch.org/religion/religious-landscape-study/state/"
    headers = {
        "User-Agent" : "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    }

    result = requests.get(url, headers=headers)
    soup = BeautifulSoup(result.content,  "html.parser")

    # get religions table:
    religions_df = pd.read_html(StringIO(str(soup.findAll("table")[1])))[0].reindex().transpose().reset_index() # we need to transpose
    religions_df.columns = religions_df.iloc[0] # Name columns post-transpose
    # religions_df = religions_df.rename({
    #     column:re.sub('[()"\\\']', '', column.strip().lower().replace(' ', '_')) for column in religions_df.columns
    # }, axis=1)
    religions_df.drop(religions_df.index[0], inplace=True) # Drop column name rows
    religions_df = religions_df.drop(religions_df.index[-1]) # drop sample size column
    religions_df = religions_df.map(lambda x: string_to_percent(x) if type(x) == str and '%' in x else x) # Convert string percentages

    # get believe in god table:
    believe_in_god_df = pd.read_html(StringIO(str(soup.findAll("table")[2])),header=0)[0]
    believe_in_god_df = believe_in_god_df.drop(["Sample\tsize"], axis=1) # Drop sample size column
    believe_in_god_df = believe_in_god_df.map(lambda x: string_to_percent(x) if type(x) == str and '%' in x else x) # Convert string percentages

    # merge tables:
    full_table = pd.merge(
        believe_in_god_df,
        religions_df,
        right_on="Religious tradition",
        left_on="State",
        how="inner"
    ).drop("Religious tradition", axis=1)

    # Get geographical data for states
    # states_geodata = geopandas.read_file('fresh_data/geodata/usa-states-census-2014.shp')

    # full_table = pd.merge(
    #     full_table,
    #     states_geodata,
    #     how="left",
    #     left_on="State",
    #     right_on="NAME"
    # )

    return full_table

# Polarization data on representatives
def load_polarization_data():

    # Load from CSV:
    voteview_polarization_df = pd.read_csv("fresh_data/member_ideology_house_all_years.csv")

    # Remove president from assessment:
    voteview_polarization_df = voteview_polarization_df[voteview_polarization_df["chamber"]=="House"]

    # Get statename from state_abbrev:
    voteview_polarization_df["state_name"] = voteview_polarization_df["state_abbrev"].apply(lambda x: state_mapping[x])

    # Drop unnecessary values:
    drop = ["occupancy", "conditional"]
    voteview_polarization_df.drop(drop, axis=1, inplace=True)

    # Rename bioname to representative for integration with other data
    voteview_polarization_df["representative"] = voteview_polarization_df["bioname"]
    voteview_polarization_df.drop("bioname", axis=1, inplace=True)

    voteview_polarization_df = voteview_polarization_df[['representative', 'congress', 'chamber', 'icpsr', 'state_icpsr', 'district_code',
       'state_abbrev', 'party_code', 'last_means', 'bioguide_id', 'born',
       'died', 'nominate_dim1', 'nominate_dim2', 'nominate_log_likelihood',
       'nominate_geo_mean_probability', 'nominate_number_of_votes',
       'nominate_number_of_errors', 'nokken_poole_dim1', 'nokken_poole_dim2',
       'state_name']]
    
    # Restrict to FEC bounds of 1990-2022
    mask_1999_2020 = (voteview_polarization_df["congress"] >= 101) & (116 >= voteview_polarization_df["congress"])
    voteview_polarization_df = voteview_polarization_df[mask_1999_2020]

    districts = ['American Samoa', 'District Of Columbia', 'Guam',
       'Puerto Rico', 'Virgin Islands', 'Northern Mariana Islands']
    
    states_mask = voteview_polarization_df["state_name"].apply(lambda x: True if x in districts else False)
    voteview_polarization_df = voteview_polarization_df.drop(voteview_polarization_df[states_mask].index)

    voteview_polarization_df["district_code"] = voteview_polarization_df["district_code"].astype(int)

    # Get the years of each congressional session:
    year = 1989
    voteview_polarization_df["year_range"] = voteview_polarization_df["congress"].apply(lambda x: f"{ year+((x-101)*2) }-{ year+((x-101)*2)+2 }")

    values = {
        "nominate_number_of_votes": 0
    }

    # Create age column
    voteview_polarization_df["age"] = voteview_polarization_df.apply(lambda x: get_age(x), axis=1)
    voteview_polarization_df.drop(["died"], axis=1, inplace=True)

    # Recode NaNs and drop rows with properly missing values:
    voteview_polarization_df = voteview_polarization_df.fillna(value=values)
    voteview_polarization_df = voteview_polarization_df[voteview_polarization_df["nominate_dim1"].notna()]

    return voteview_polarization_df

# Census data on poverty
def load_census_poverty_data():
    # Load from CSV:
    saipe_df = pd.read_excel("irs.xls",skiprows=2)

    congress = 101
    saipe_df["congress"] = saipe_df["Year"].apply(lambda x: congress+((x-1989)//2))
    saipe_df[["Year", "congress"]].head(5) # Let's view the year and congress mappings to ensure they are accurate:

    # Average values by congressional session and combine rows (using the average)
    # Drop year and State FIPS code, lowercase columns, reorganize
    saipe_df_clean = pd.DataFrame()
    for congress in saipe_df["congress"].unique():
        df_congress = saipe_df[saipe_df["congress"] == congress].groupby("Name").mean()
        df_congress.reset_index(inplace=True)
        df_congress["year_range"] = df_congress["Year"].apply(lambda x: f"{int(x-0.5)}-{int(x+1.5)}") # Fix year formatting
        df_congress["year_range_open_secrets"] = df_congress["Year"].apply(lambda x: f"{int(x-0.5)}-{int(x+.5)}") # Add year formatting for openSecrets
        df_congress["state_FIPS"] = df_congress["State FIPS code"].astype(int) # cast to int instead of float
        df_congress["congress"] = df_congress["congress"].astype(int)
        df_congress.drop(["Year", "State FIPS code"],axis=1,inplace=True) # Remove outdated year and FIPS code columns

        new_columns = {old_name:old_name.lower() for old_name in df_congress.columns} # lowercase columns
        new_columns["Name"] = "state_name" # rename "name" to more accurate "state_name"
        df_congress = df_congress.rename(columns=new_columns)
        df_congress = df_congress[["congress", "year_range", "state_name", "state_fips", 'total exemptions', 'poor exemptions',
        'age 65 and over exemptions', 'age 65 and over poor exemptions',
        'child exemptions', 'poor child exemptions', 'year_range_open_secrets',
        'total exemptions under age 65', 'poor exemptions under age 65',
        'median agi', 'mean agi']] # reorganize dataframe
        
        saipe_df_clean = pd.concat([saipe_df_clean,df_congress],ignore_index=True)

    # Re-casting averaged values into whole numbers
    for column in saipe_df_clean.columns:
        if saipe_df_clean[column].dtype == float:
            saipe_df_clean[column] = saipe_df_clean[column].astype(int)

    # Remove district of columbia
    columbia_filter = saipe_df_clean["state_name"] == "District of Columbia"
    saipe_df_clean.drop(saipe_df_clean[columbia_filter].index,inplace=True)

    return saipe_df_clean

# Financial data including spending
def load_open_secrets_data(root):
    dir = root

    first_year=1999

    full_df = pd.DataFrame()
    for year in range(first_year, 2021, 2):
        year_range = f"{year}-{year+1}"

        cash_filename=f"/cash/Who Has the Most Cash on Hand_ House Incumbents, {year_range}.csv"
        cash_year_df = pd.read_csv(dir+cash_filename)
        cash_year_df["year_range"] = year_range
    
        raised_filename=f"/raised/Who Raised the Most_ House Incumbents, {year_range}.csv"
        raised_year_df = pd.read_csv(dir+raised_filename)
        raised_year_df["year_range"] = year_range

        spent_filename=f"/spent/Who Spent the Most_ House Incumbents, {year_range}.csv"
        spent_year_df = pd.read_csv(dir+spent_filename)
        spent_year_df["year_range"] = year_range

        cash_and_raised = pd.merge(
            cash_year_df,
            raised_year_df,
            on=["Representative", "Office Running For", "year_range"]
        )

        all_features = pd.merge(
            spent_year_df,
            cash_and_raised,
            on=["Representative", "Office Running For", "year_range"]
        )

        full_df = pd.concat([full_df, all_features],ignore_index=True)

    # We want

    monetary_fields = ["Total Spent", "Cash on Hand", "Total Raised"]
    for monetary_field in monetary_fields:
        full_df[monetary_field] = full_df[monetary_field].apply(lambda x: int(re.sub("[$,]", "",x)))

    # Remove the state/party suffix:
    full_df["representative"] = full_df["Representative"].apply(lambda x: "".join(x.split('(')[0]).strip())

    full_df["state_name"] = full_df["Office Running For"].apply(lambda x: ''.join(x.split()[:-2]))
    full_df["district_code"] = full_df["Office Running For"].apply(lambda x: ''.join(x.split()[-1]))

    # Drop "Office Running For" as we have this info in state_name and district_code, and "Representative" which is now lowercase
    full_df = full_df.drop(["Office Running For", "Representative"], axis=1)

    return full_df

# State demographic data
def load_KFF_data(root):
    # https://www.kff.org/other/state-indicator/total-residents/?currentTimeframe=0&sortModel=%7B%22colId%22:%22Location%22,%22sort%22:%22asc%22%7D

    filenames = {
        "" : "2022",
        " (1)" : "2021",
        " (2)" : "2019",
        " (3)" : "2018",
        " (4)" : "2017",
        " (5)" : "2016",
        " (6)" : "2015",
        " (7)" : "2014",
        " (8)" : "2013",
        " (9)" : "2012",
        " (10)" : "2011",
        " (11)" : "2010",
        " (12)" : "2009",
        " (13)" : "2008",
    }

    full_kff = pd.DataFrame()

    for key,value in filenames.items():
        year_poverty = pd.read_csv(root+"poverty/"+f"raw_data{key}.csv",skiprows=2,skipfooter=20,engine="python").drop(["Footnotes"],axis=1)
        year_race = pd.read_csv(root+"race/"+f"raw_data{key}.csv",skiprows=2,skipfooter=20,engine="python").drop(["Footnotes","Total"],axis=1)

        year_poverty_race = pd.merge(
            year_poverty,
            year_race,
            how="inner",
            on="Location"
        )

        year_poverty_race["year"] = int(value)

        year_poverty_race.rename({
            column:column.strip().lower().replace(' ', '_') for column in year_poverty_race.columns
        }, axis=1, inplace=True)

        full_kff = pd.concat([full_kff, year_poverty_race],ignore_index=True)


    for column in [num_column for num_column in full_kff.columns if num_column not in ["location", "year"]]:
        full_kff[column] = full_kff[column].apply(lambda x: np.nan if type(x) != float and "<" in x else float(x))
        if bool(re.search(r'\d', column)):
            full_kff = full_kff.rename({column:"poverty_"+column},axis=1)

    values = {column:0 for column in full_kff.columns}

    # Recode NaNs and drop rows with properly missing values:
    full_kff = full_kff.fillna(value=values)

    return full_kff

# Financial data on representatives
def load_FEC_data(root):
    dir = root

    full_df = pd.DataFrame()
    for year in range(1990, 2022, 2):
        year_range = f"{year-1}-{year+1}" # for whatever reason, the files save as the "last" year

        FEC_filename = f"ConCand4_{year}_24m.xlsx"
        FEC_year_df = pd.read_excel(dir+FEC_filename,skiprows=4)
        FEC_year_df["year_range"] = year_range

        full_df = pd.concat([full_df, FEC_year_df],ignore_index=True)

    full_df.drop(["Coverage End Date"],axis=1, inplace=True)

    drop_mask = (~pd.isna(full_df["Candidate"])) & (~pd.isna(full_df["District"]))
    full_df = full_df[drop_mask]

    full_df["District"] = full_df["District"].astype(int)

    # Alaska and Delaware have only one house seat each in the House of Congress. The FEC reports this district as "00", but the US census and our polarization data both identify it as "1". We will need to make this change to merge appropriately down the line:
    single_seat_state_mask = (full_df["District"] == 00)
    full_df.loc[single_seat_state_mask, "District"] = 1

    # remove whitespaces
    full_df = full_df.map(lambda x: x.strip() if isinstance(x, str) else x)

    columns = {
        'year_range' : "year_range",
        'State' : "state_name",
        'District' : "district_code",
        'Candidate' : "representative",
        'Party' : "party",
        'Incumbent/\nChallenger/Open' : "running_as",
        'Receipts' : "receipts",
        'Contributions \nfrom Individuals' : "contributions_from_individuals",
        'Contributions\nfrom PACs and\nOther Committees' : "contributions_from_pacs",
        'Contributions and\nLoans from \n the Candidate' : "contributions_and_loans_from_candidate",
        'Disbursements' : "disbursements",
        'Cash On Hand' : "cash_on_hand",
        'Debts' : "debts",  
    }
    full_df = full_df.rename(columns=columns)[['year_range', 'state_name', 'district_code', 'representative', 'party', 'running_as', 'receipts',
        'contributions_from_individuals', 'contributions_from_pacs',
        'contributions_and_loans_from_candidate', 'disbursements',
        'cash_on_hand', 'debts']]
    
    # Get session of congress from year
    congress = 101
    full_df["congress"] = full_df["year_range"].apply(lambda x: congress+((int(x[:4])-1989)//2))

    # Remove districts, non-state entities with no voting power in congress:
    districts = ['District Of Columbia', 'American Samoa', 'Guam', 'Northern Mariana', 'Puerto Rico', 'Virgin Islands']
    states_mask = full_df["state_name"].apply(lambda x: True if x in districts else False)
    full_df = full_df.drop(full_df[states_mask].index)

    # Manually reconcile redistricts:

    # In 2013, AZ's 8th district became the 2nd, and VoteView expects the update:
    redistrict_mask = (full_df["year_range"] == "2011-2013") & (full_df["representative"] == "BARBER, RONALD")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 8

    # In 2013, NY's parts of 26th district became the 27th district, but Kathy Hochul occupied the 26th district, not the 27th.:
    redistrict_mask = (full_df["year_range"] == "2011-2013") & (full_df["representative"] == "HOCHUL, KATHLEEN COURTNEY")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 26

    # In 2003, the NY's 31st district was redistricted into the 29th district. Houghton Amory Jr. represented the 31st at this time:
    redistrict_mask = (full_df["year_range"] == "2001-2003") & (full_df["representative"] == "HOUGHTON, AMORY")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 31

    # Conor Lamb switched districts in 2019, but the FEC reports his old district
    redistrict_mask = (full_df["year_range"] == "2017-2019") & (full_df["representative"] == "LAMB, CONOR")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 18

    # Taylor Eugene's 5th district was redistricted to the 4th in 2000. The FEC records this too late:
    redistrict_mask = (full_df["year_range"] == "2001-2003") & (full_df["representative"] == "TAYLOR, GARY EUGENE (GENE)")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 5

    # Steven Latourette's district was redistricted to the 17th in 1992. FEC records this too late:
    redistrict_mask = (full_df["year_range"] == "2001-2003") & (full_df["representative"] == "LATOURETTE, STEVEN C")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 19

    # Sander Levin's 17th district was redistricted to the 12th in 1992. FEC records this too late:
    redistrict_mask = (full_df["year_range"] == "1991-1993") & (full_df["representative"] == "LEVIN, SANDER")
    full_df.loc[full_df[redistrict_mask].index, "district_code"] = 17


    # Replace NaNs:
    values = {column:0 for column in full_df.columns}
    values["party"] = "No Party Affiliation"

    # Recode NaNs and drop rows with properly missing values:
    full_df = full_df.fillna(value=values)

    return full_df

def load_all_data(root="fresh_data"):

    voteview_polarization_df = load_polarization_data()
    saipe_df_clean = load_census_poverty_data()

    df = pd.merge(
        saipe_df_clean,
        voteview_polarization_df,
        how="left",
        on=["congress", "state_name"]
    ).reset_index().drop(["chamber","index"], axis=1)

    parties = get_parties()
    df["party_name"] = df["party_code"].apply(lambda x: parties[x])

    # Create age column
    df["age"] = df.apply(lambda x: get_age(x), axis=1)
    df.drop(["died"], axis=1, inplace=True)

    # Shuffle columns around
    df = df[['congress', 'bioname', 'party_code', 'party_name', 'age', 'born',
       'year_range', 'state_name', 'state_abbrev', 'district_code', 'icpsr', 
       'state_icpsr', 'state_fips', 'nominate_dim1', 'nominate_dim2',
       'nominate_log_likelihood', 'nominate_geo_mean_probability',
       'nominate_number_of_votes', 'nominate_number_of_errors',
       'nokken_poole_dim1', 'nokken_poole_dim2', 'total exemptions',
       'poor exemptions', 'age 65 and over exemptions',
       'age 65 and over poor exemptions', 'child exemptions',
       'poor child exemptions', 'total exemptions under age 65',
       'poor exemptions under age 65', 'median agi', 'mean agi', 'year_range_open_secrets']]

    # Remove the three missing values:
    df.drop(df[df["nominate_dim1"].isna()].index, inplace=True)

    # # Add OpenSecret data:
    # opened_secrets = load_open_secrets_data(root)

    # left_on = ["bioname", "district_code", "state_name", "year_range_open_secrets"]
    # right_on = ["Representative", "district_code", "state_name", "year_range"]

    # df = fuzzy_left_join(df, opened_secrets, left_on, right_on)

    return df