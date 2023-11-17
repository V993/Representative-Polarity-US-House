
import re
import pandas as pd
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
    parties_df = pd.read_csv("HSall_parties.csv")
    parties_df = parties_df.groupby(['party_code','party_name'])["n_members"].sum().reset_index().rename(columns={'n_members':'count_all_time'})
    return {party_code:parties_df[parties_df["party_code"] == party_code]["party_name"].item() for party_code in parties_df["party_code"].unique()}

def get_populations(root):
    total_population_df = pd.read_excel(root+"/population-change-data-table.xlsx", skiprows=4).rename({"Unnamed: 0": "Area"}, axis=1)
    total_population_df.head()

    total_population_1970_2020 = total_population_df.loc[:,["Area"]]

    for year in [2020, 2010, 2000, 1990, 1980, 1970]:
        total_population_1970_2020.loc[:, f"{year}_pop"] = total_population_df.loc[:,f"Resident Population {year} Census"]

    return total_population_1970_2020

def load_polarization_data():

    # Load from CSV:
    voteview_polarization_df = pd.read_csv("member_ideology_house_all_years.csv")

    # Remove president from assessment:
    voteview_polarization_df = voteview_polarization_df[voteview_polarization_df["chamber"]=="House"]

    # Get statename from state_abbrev:
    voteview_polarization_df["state_name"] = voteview_polarization_df["state_abbrev"].apply(lambda x: state_mapping[x])

    # Drop unnecessary values:
    drop = ["occupancy", "conditional"]
    voteview_polarization_df.drop(drop, axis=1, inplace=True)

    voteview_polarization_df["district_code"] = voteview_polarization_df["district_code"].astype(int)

    return voteview_polarization_df

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

    monetary_fields = ["Total Spent", "Cash on Hand", "Total Raised"]
    for monetary_field in monetary_fields:
        full_df[monetary_field] = full_df[monetary_field].apply(lambda x: int(re.sub("[$,]", "",x)))

    full_df["state_name"] = full_df["Office Running For"].apply(lambda x: ''.join(x.split()[:-2]))
    full_df["district_code"] = full_df["Office Running For"].apply(lambda x: ''.join(x.split()[-1]))

    return full_df

def load_KFF_data(root):
    dir = "KFF"

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
        year_poverty = pd.read_csv("poverty/"+f"raw_data{key}.csv",skiprows=2,skipfooter=20,engine="python").drop(["Footnotes"],axis=1)
        year_race = pd.read_csv("race/"+f"raw_data{key}.csv",skiprows=2,skipfooter=20,engine="python").drop(["Footnotes","Total"],axis=1)

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

    return full_kff

def load_FEC_data(root):
    dir = root

    full_df = pd.DataFrame()
    for year in range(1990, 2023, 2):
        year_range = f"{year-1}-{year+1}" # for whatever reason, the files save as the "last" year

        FEC_filename = f"ConCand4_{year}_24m.xlsx"
        FEC_year_df = pd.read_excel(dir+FEC_filename,skiprows=4)
        FEC_year_df["year_range"] = year_range

        full_df = pd.concat([full_df, FEC_year_df],ignore_index=True)

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