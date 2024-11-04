import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pymongo import MongoClient
from scipy import stats

class MongoDBService:
    def __init__(self, connection_string):
        self.client = MongoClient(connection_string)
        self.db = self.client.get_database()
        
    def find_all(self, collection_name):
        return list(self.db[collection_name].find())

def interpret_distribution(data):
    """Interpret the shape and characteristics of a numerical distribution"""
    # Calculate skewness and kurtosis
    skewness = stats.skew(data.dropna())
    kurtosis = stats.kurtosis(data.dropna())
    
    # test for normality
    _, p_value = stats.shapiro(data.dropna())
    
    interpretation = []
    
    # Interpret skewness
    if abs(skewness) < 0.5:
        interpretation.append("approximately symmetric")
    elif skewness < 0:
        interpretation.append("negatively skewed (tail extends to the left)")
    else:
        interpretation.append("positively skewed (tail extends to the right)")
    
    # Interpret kurtosis
    if abs(kurtosis) < 0.5:
        interpretation.append("normal-like peaked")
    elif kurtosis < 0:
        interpretation.append("flatter than normal distribution")
    else:
        interpretation.append("more peaked than normal distribution")
    
    # Interpret normality test
    if p_value < 0.05:
        interpretation.append("not normally distributed (p < 0.05)")
    else:
        interpretation.append("approximately normally distributed (p >= 0.05)")
    
    return ", ".join(interpretation)

def interpret_outliers(data):
    """Interpret the presence and significance of outliers"""
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    outliers = data[(data < lower_bound) | (data > upper_bound)]
    outlier_percentage = (len(outliers) / len(data)) * 100
    
    if len(outliers) == 0:
        return "No outliers detected"
    else:
        return f"Contains {len(outliers)} outliers ({outlier_percentage:.1f}% of data)"

def interpret_categorical_distribution(value_counts):
    """Interpret the distribution of categorical variables"""
    total = value_counts.sum()
    dominant_category = value_counts.index[0]
    dominant_percentage = (value_counts.iloc[0] / total) * 100
    
    interpretation = []
    interpretation.append(f"Most common category: '{dominant_category}' ({dominant_percentage:.1f}%)")
    
    # Calculate entropy for diversity measure
    probabilities = value_counts / total
    entropy = -(probabilities * np.log2(probabilities)).sum()
    max_entropy = np.log2(len(value_counts))
    diversity_ratio = entropy / max_entropy if max_entropy > 0 else 0
    
    if diversity_ratio < 0.3:
        interpretation.append("highly concentrated distribution")
    elif diversity_ratio < 0.7:
        interpretation.append("moderately diverse distribution")
    else:
        interpretation.append("highly diverse distribution")
    
    return ", ".join(interpretation)

def analyze_data(mongodb_service, collection_name):
    # Load data
    df = pd.DataFrame(mongodb_service.find_all(collection_name))
    
    if df.empty:
        print(f"No data found in collection '{collection_name}'")
        return
    
    if '_id' in df.columns:
        df = df.drop('_id', axis=1)
    
    # Basic information with interpretation
    print("\n=== Basic Data Information ===")
    print(f"\nDataset Shape: {df.shape}")
    print(f"Interpretation: Dataset contains {df.shape[0]} records with {df.shape[1]} variables")
    
    print("\nColumns:", df.columns.tolist())
    print("\nData Types:")
    print(df.dtypes)
    
    # Missing Values Analysis with interpretation
    print("\n=== Missing Value Analysis ===")
    missing_values = df.isnull().sum()
    missing_percentage = (missing_values / len(df)) * 100
    missing_info = pd.DataFrame({
        'Missing Values': missing_values,
        'Percentage': missing_percentage
    })
    missing_cols = missing_info[missing_info['Missing Values'] > 0]
    
    if not missing_cols.empty:
        print("\nMissing Values Found:")
        print(missing_cols)
        print("\nInterpretation:")
        for idx, row in missing_cols.iterrows():
            if row['Percentage'] < 5:
                print(f"- {idx}: Minor missing data ({row['Percentage']:.1f}%), consider mean/median imputation")
            elif row['Percentage'] < 20:
                print(f"- {idx}: Moderate missing data ({row['Percentage']:.1f}%), investigate pattern of missingness")
            else:
                print(f"- {idx}: Significant missing data ({row['Percentage']:.1f}%), consider variable removal or advanced imputation")
    else:
        print("No missing values found in the dataset")
    
    # Numerical Analysis with interpretation
    print("\n=== Numerical Analysis ===")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if not numeric_cols.empty:
        print("\nDescriptive Statistics:")
        stats_df = df[numeric_cols].describe()
        print(stats_df)
        
        print("\nStatistical Interpretation:")
        for col in numeric_cols:
            print(f"\n{col}:")
            print(f"- Distribution: {interpret_distribution(df[col])}")
            print(f"- Outliers: {interpret_outliers(df[col])}")
            print(f"- Range: from {stats_df[col]['min']:.2f} to {stats_df[col]['max']:.2f}")
            print(f"- Center: mean={stats_df[col]['mean']:.2f}, median={stats_df[col]['50%']:.2f}")
            
        # Visualizations remain the same
        plt.figure(figsize=(15, 5 * ((len(numeric_cols) + 1) // 2)))
        for idx, col in enumerate(numeric_cols, 1):
            plt.subplot((len(numeric_cols) + 1) // 2, 2, idx)
            sns.histplot(df[col], kde=True)
            plt.title(f'Distribution of {col}')
            plt.xlabel(col)
        plt.tight_layout()
        plt.show()
        
        plt.figure(figsize=(15, 5 * ((len(numeric_cols) + 1) // 2)))
        for idx, col in enumerate(numeric_cols, 1):
            plt.subplot((len(numeric_cols) + 1) // 2, 2, idx)
            sns.boxplot(y=df[col])
            plt.title(f'Box Plot of {col}')
        plt.tight_layout()
        plt.show()
    
    # Categorical Analysis with interpretation
    categorical_cols = df.select_dtypes(include=['object']).columns
    if not categorical_cols.empty:
        print("\n=== Categorical Analysis ===")
        for col in categorical_cols:
            print(f"\nAnalysis of {col}:")
            value_counts = df[col].value_counts()
            print("\nValue Counts:")
            print(value_counts)
            print("\nInterpretation:")
            print(interpret_categorical_distribution(value_counts))
            
            plt.figure(figsize=(10, 6))
            sns.barplot(x=value_counts.index, y=value_counts.values)
            plt.title(f'Distribution of {col}')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.show()

def main():
    try:
        connection_string = "mongodb://localhost:27017/TailoringDb"
        mongodb_service = MongoDBService(connection_string=connection_string)
        
        print("Analyzing materials price updates...")
        analyze_data(mongodb_service, "materials_price_updates")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if 'mongodb_service' in locals():
            mongodb_service.client.close()

if __name__ == "__main__":
    main()