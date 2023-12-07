import re
import numpy as np
import pandas as pd
from thefuzz import fuzz
from math import floor, ceil
import matplotlib.pyplot as plt
import fresh_data.get_datasets
import importlib
importlib.reload(fresh_data.get_datasets) # reload get_datasets every time this cell is run
from fresh_data.get_datasets import *

## Helpers:
def merge_decennial(x,year_population_df,year):
    state_population_in_year = year_population_df[year_population_df["Area"] == x["location"]].iloc[0][year]
    x["population"] = state_population_in_year
    return x

def get_decennial_year(year):
    return str(year[:-1]+"0")

def jaro_distance(s1, s2) :

	# If the strings are equal 
	if (s1 == s2) :
		return 1.0; 

	# Length of two strings 
	len1 = len(s1);
	len2 = len(s2); 

	if (len1 == 0 or len2 == 0) :
		return 0.0; 

	# Maximum distance upto which matching 
	# is allowed 
	max_dist = (max(len(s1), len(s2)) // 2 ) - 1; 

	# Count of matches 
	match = 0; 

	# Hash for matches 
	hash_s1 = [0] * len(s1) ;
	hash_s2 = [0] * len(s2) ; 

	# Traverse through the first string 
	for i in range(len1) : 

		# Check if there is any matches 
		for j in range( max(0, i - max_dist), 
					min(len2, i + max_dist + 1)) : 
			
			# If there is a match 
			if (s1[i] == s2[j] and hash_s2[j] == 0) : 
				hash_s1[i] = 1; 
				hash_s2[j] = 1; 
				match += 1; 
				break; 
		
	# If there is no match 
	if (match == 0) :
		return 0.0; 

	# Number of transpositions 
	t = 0; 

	point = 0; 

	# Count number of occurrences 
	# where two characters match but 
	# there is a third matched character 
	# in between the indices 
	for i in range(len1) : 
		if (hash_s1[i]) :

			# Find the next matched character 
			# in second string 
			while (hash_s2[point] == 0) :
				point += 1; 

			if (s1[i] != s2[point]) :
				point += 1;
				t += 1;
			else :
				point += 1;
				
		t /= 2; 

	# Return the Jaro Similarity 
	return ((match / len1 + match / len2 +
			(match - t) / match ) / 3.0); 

def jaro_winkler(s1, s2) : 
    # Function to calculate the Jaro Winkler Similarity of two strings 
    # code from https://www.geeksforgeeks.org/jaro-and-jaro-winkler-similarity/#

	jaro_dist = jaro_distance(s1, s2); 

	# If the jaro Similarity is above a threshold 
	if (jaro_dist > 0.7) :

		# Find the length of common prefix 
		prefix = 0; 

		for i in range(min(len(s1), len(s2))) :
		
			# If the characters match 
			if (s1[i] == s2[i]) :
				prefix += 1; 

			# Else break 
			else :
				break; 

		# Maximum of 4 characters are allowed in prefix 
		prefix = min(4, prefix); 

		# Calculate jaro winkler Similarity 
		jaro_dist += 0.1 * prefix * (1 - jaro_dist); 

	return jaro_dist*100; 


## Entity Resolution:
def fuzzy_entity_res(rep_1, rep_2):
    """
        Returns an integer prediction of how close two strings are in similarity.
        100 is the highest level of similarity. 0 is the lowest.
    """
    if pd.isna(rep_2):
        return 0
    
    rep_1 = re.sub('[(),.]','',rep_1).lower().strip()
    rep_2 = re.sub('[(),.]','',rep_2).lower().strip()
    prediction = fuzz.partial_ratio(rep_1, rep_2)

    if prediction < 70: # Try using Jaro Winkler:
        prediction = jaro_winkler(rep_1, rep_2)
    return prediction

def get_match_subset(df_2, row_1, year_change):
    # get subset of df_2 with matches in state and district, with current session:

    match_area = (df_2["state_name"] == row_1["state_name"]) & (df_2["district_code"] == row_1["district_code"])
    df_2_subset = df_2[match_area & (df_2["congress"] == row_1["congress"]+year_change)]
    return df_2_subset

def check_subset(row_1, df_2, suffix_1, suffix_2):
    """
        Perform entity resolution on a record in the polarize and census df 
        Only parses a subset of the FEC df which has matches in state, and district
        Then uses The Fuzz(TM) to find the best match within the subset.
    """

    closest_str, congress_str, subset_str = "", "", ""

    for year_change in [0, -1, +1]:
        # get subset of df_2 with matches in state and district, with approximate time period:
        df_2_subset = get_match_subset(df_2, row_1, year_change)
        
        if len(df_2_subset) == 0:
            if year_change == -1:
                closest_str = f"ERROR - {row_1['representative']}"
                congress_str = f"no matches for congresses {row_1['congress']-1}-{row_1['congress']+1} | district: {row_1['district_code']}"
            continue

        df_2_subset[f"distance_{suffix_1}_{suffix_2}"] = df_2_subset.apply(lambda row_2: fuzzy_entity_res(row_1[f"representative_{suffix_1}"], row_2[f"representative_{suffix_2}"]), axis=1)

        # display(df_2_subset)

        closest_match_row = df_2_subset[df_2_subset[f"distance_{suffix_1}_{suffix_2}"]==df_2_subset[f"distance_{suffix_1}_{suffix_2}"].max()].iloc[0] # Get closest match
        row_1[f"{suffix_1}-{suffix_2}_closeness"] = df_2_subset[f'distance_{suffix_1}_{suffix_2}'].max()
        if df_2_subset[f"distance_{suffix_1}_{suffix_2}"].max() < 69: # SHAW, Eugene Clay, Jr. - fec: SHAW, E CLAY JR is scored as 69, this should be a match.

            # Save to be logged if we couldn't find a match in the other sessions of congress
            closest_str = f"no match, closest: {df_2_subset[f'distance_{suffix_1}_{suffix_2}'].max()}, for {suffix_1}: {row_1[f'representative_{suffix_1}']} - for {suffix_2}: {closest_match_row[f'representative_{suffix_2}']}"
            congress_str = f"congress: {row_1['congress']} | district: {row_1['district_code']}"
            subset_str = f"{df_2_subset[['representative', 'congress']]}"
        else: # if we have a match above 70, replace instantiated values with values from row_2
            # print(f"match, on closest: {df_2_subset[f'distance_{suffix_1}_{suffix_2}'].max()}, for {row_1[f'representative_{suffix_1}']} - {closest_match_row[f'representative_{suffix_2}']}")
            for column in [column for column in df_2_subset.columns if column not in row_1.index.to_list()]+["year_range"]:
                row_1[column] = closest_match_row[column]
                row_1["fail"] = False
            row_1["fec_year_range"] = closest_match_row["year_range"] # This is not necessarily the same period as the session of congress
            return row_1
        
    # Log failures:
    # print(closest_str)
    # print(congress_str)
    # print(subset_str)
    for column in [column for column in df_2_subset.columns if column not in row_1.index.to_list()]:
        row_1[column] = np.nan
        row_1["fail"] = True 
    return row_1
        
def fuzzy_merge(df_1, df_2, suffix_1, suffix_2):
    # Apply merge algorithm on each record of df_1
    df_1.loc[:, f"representative_{suffix_1}"] = df_1["representative"]
    df_2.loc[:, f"representative_{suffix_2}"] = df_2["representative"]

    # Only include matches, remove all failed matches (NaNs):
    match_df = df_1.apply(lambda row_1: check_subset(row_1, df_2, suffix_1, suffix_2), axis=1)
    # return match_df[~pd.isna(match_df["representative"])]
    return match_df

def get_representative_information():
    """
    Returns a dataframe composed of data from the following sources:
        - VoteView polarization data
        - FEC financial contributions for candidates
    """

    polarization = load_polarization_data()
    fec = load_FEC_data("FEC/")

    polarize_and_fec = fuzzy_merge(polarization, fec, "polarization", "fec")

    return polarize_and_fec
	
def get_state_demographics():
    """
    Returns a dataframe composed of data from the following sources:
        - KFF (Kaiser Family Foundation) Data on State demographics (race, poverty)
        - Census Decennial demographics (total population)
        - PEW Research Center (religious populations)
    """

    # Load KFF demographics data
    kff = load_KFF_data("KFF/")
    us_mask = kff[kff["location"]=="United States"].index
    kff = kff.drop(us_mask)

    # Load total population data per state
    total_population = get_populations("census_demographics")

    # load religions per state
    religions = get_religions_and_geography()

    # Merge KFF and population:
    kff = kff.apply(lambda x: merge_decennial(x, total_population[["Area", get_decennial_year(str(x["year"]))]], get_decennial_year(str(x["year"]))),axis=1)

    # Merge KFF and religions:

    state_demographics = pd.merge(
        kff,
        religions,
        how="left",
        left_on="location",
        right_on="State"
    )

    return state_demographics

## Merge State and Representative Tables:
def merge_state_and_reps(row_1, df_2):
    # Match based on year and state:
    mask_state = (df_2["location"] == row_1["state_name"])
    if int(row_1["year_range"][-4:]) < 2008: # Use 2008 stats for anything older than 2008 due to data unavailability
        mask_2008 = (df_2['year'] == 2008)
        subset = df_2[mask_2008 & mask_state]
    else:
        mask_year = (df_2["year"] >= int(row_1["year_range"][:4])) & (df_2['year'] <= int(row_1["year_range"][-4:]))
        subset = df_2[mask_year & mask_state]
        # The entire subset is a match, so we will aggregate the years into average values for the year_range:

    # print(subset)
    match_row = (subset.mean(axis=0, numeric_only=True).round(3))
    # print(match_row)
    # print(subset.groupby("location").mean())

    return pd.concat([row_1, match_row],axis=0)


## Main:
def get_df():
    """
    Returns a dataframe with the merged tables from the following sources:
        State Demographics:
            - KFF (Kaiser Family Foundation) Data on State demographics (race, poverty)
            - Census Decennial demographics (total population)
            - PEW Research Center (religious populations)
        Representative Information:
            - VoteView polarization data
            - FEC financial contributions for candidates
    """

    ## Load and merge tables:

    # Get state demographics:
    state_demographics_table = get_state_demographics()

    # Get representative information: 
    representative_table = get_representative_information()

    # Apply merge on representative table using helper entity resolution function:
    full_df = representative_table.apply(lambda row_1: merge_state_and_reps(row_1, state_demographics_table), axis=1)

    # # Apply geolocation data to each row's state:
    # states_geodata = geopandas.read_file('fresh_data/geodata/usa-states-census-2014.shp')

    # full_df = pd.merge(
    #     full_df,
    #     states_geodata,
    #     how="left",
    #     left_on="state_name",
    #     right_on="NAME"
    # )

    ## Final cleaning:

    # Drop unnecessary columns:
    drop = ["fail", "chamber", "distance_polarization_fec", "year", "party_code", "state_abbrev"]
    full_df.drop(drop, axis=1, inplace=True)

    # Clean up values:
    full_df["congress"] = full_df["congress"].astype(str)
    full_df["district_code"] = full_df["district_code"].astype(str)

    # Rename poverty stat:
    full_df["total_poverty"] = full_df["total"]
    full_df.drop("total",inplace=True,axis=1)

    # Rename/Reorganize columns:
    columns = [
        # Polarization
        "representative", "state_name", "district_code", "party", "congress", "year_range",
        "born", "age", "nominate_dim1", "nominate_dim2", "nominate_number_of_votes", 
        "representative_polarization", "representative_fec", "polarization-fec_closeness",
        
        # FEC
        "running_as", "receipts", "contributions_from_individuals",
        "contributions_from_pacs", "contributions_and_loans_from_candidate",
        "disbursements", "cash_on_hand", "debts", 

        # State demographics
        "poverty_children_0-18", "poverty_adults_19-64", "poverty_65+", "total_poverty", 
        
        "white", "black", "hispanic", "asian", "american_indian/alaska_native",
        "native_hawaiian/other_pacific_islander", "multiple_races", 

        "Believe in God; absolutely certain",
        "Believe in God; fairly certain",
        "Believe in God; not too/not at all certain",
        "Believe in God; don't know", "Do not believe in God",
        "Other/don't know if they believe in God", 

        "Buddhist", "Catholic", "Evangelical Protestant", "Hindu", 
        "Historically Black Protestant", "Jehovah's Witness", "Jewish", 
        "Mainline Protestant", "Mormon", "Muslim", "Orthodox Christian", "Unaffiliated (religious \"nones\")",
        "population",

        # Geodata:
        'STATEFP', 'STATENS', 'AFFGEOID', 'GEOID', 'STUSPS', 'NAME', 'LSAD', 'region', 'geometry'
    ]

    full_df = full_df[columns]

    full_df = full_df.rename({
        column:re.sub("['();\\\"]", '', column.strip().lower()).replace(' ', '_').replace('/', '_') for column in columns
    }, axis=1)

    # convert int values to objects for processing:
    for column in [ "district_code", "congress",  "born" ]: 
        full_df[column] = full_df[column].astype(str)

    # Replace NaNs in FEC:
    values = {column:0 for column in load_FEC_data("FEC/").columns}
    values["party"] = "No Party Affiliation"

    # Recode NaNs and drop rows with properly missing values:
    full_df = full_df.fillna(value=values)
    full_df.isna().sum()

    return full_df