import matplotlib.pyplot as plt
import seaborn as sns
from pymongo import MongoClient
from scipy import stats
import pandas as pd
from bson import ObjectId
import numpy as np


class MongoDBService:
    def __init__(self, connection_string):
        self.client = MongoClient(connection_string)
        self.db = self.client.get_database()
        
    def find_all(self, collection_name):
        return list(self.db[collection_name].find())

def parse_mongo_date(date_str):
    """Parse MongoDB/JavaScript date format to datetime"""
    if pd.isna(date_str):
        return None
    # Extract the date part before GMT
    try:
        # Handle different possible formats
        if isinstance(date_str, str):
            if 'GMT' in date_str:
                date_str = date_str.split('GMT')[0].strip()
            return pd.to_datetime(date_str, format='%a %b %d %Y %H:%M:%S')
        else:
            return pd.to_datetime(date_str)
    except:
        return None

def analyze_workmanship_distribution(workmanship_scores):
    """Analyze the distribution of workmanship scores"""
    if len(workmanship_scores) < 2:
        return "insufficient data for distribution analysis"
        
    mean_score = np.mean(workmanship_scores)
    median_score = np.median(workmanship_scores)
    std_score = np.std(workmanship_scores)
    
    interpretation = []
    
    # Analyze central tendency
    if abs(mean_score - median_score) < 5:
        interpretation.append("scores are symmetrically distributed")
    elif mean_score > median_score:
        interpretation.append("scores are positively skewed (some high outliers)")
    else:
        interpretation.append("scores are negatively skewed (some low outliers)")
    
    # Analyze spread
    if std_score < 5:
        interpretation.append("very consistent workmanship scores")
    elif std_score < 10:
        interpretation.append("moderately variable workmanship scores")
    else:
        interpretation.append("highly variable workmanship scores")
    
    return ", ".join(interpretation)

def analyze_time_efficiency(time_taken, workmanship):
    """Analyze relationship between time taken and workmanship"""
    if len(time_taken) < 2 or len(workmanship) < 2:
        return "insufficient data for time efficiency analysis"
        
    correlation = stats.pearsonr(time_taken, workmanship)[0]
    
    if abs(correlation) < 0.2:
        return "minimal relationship between time and workmanship"
    elif correlation > 0:
        return f"positive correlation ({correlation:.2f}): higher workmanship tends to take more time"
    else:
        return f"negative correlation ({correlation:.2f}): quicker work associated with higher workmanship"

def analyze_product_complexity(materials_count, workmanship):
    """Analyze relationship between product complexity and workmanship"""
    if len(materials_count) < 2 or len(workmanship) < 2:
        return "insufficient data for complexity analysis"
        
    correlation = stats.pearsonr(materials_count, workmanship)[0]
    
    if abs(correlation) < 0.2:
        return "product complexity has little impact on workmanship"
    elif correlation > 0:
        return f"positive correlation ({correlation:.2f}): complex products tend to have higher workmanship"
    else:
        return f"negative correlation ({correlation:.2f}): simpler products tend to have higher workmanship"

def analyze_workmanship_data(mongodb_service):
    # Load data
    orders = pd.DataFrame(mongodb_service.find_all("orders"))
    products = pd.DataFrame(mongodb_service.find_all("products"))
    
    # Check if data exists
    if orders.empty:
        print("No orders found in database")
        return
    if products.empty:
        print("No products found in database")
        return
        
    # Print raw data info for debugging
    print("\nDebug Information:")
    print(f"Total orders: {len(orders)}")
    print("Orders columns:", orders.columns.tolist())
    print(f"\nTotal products: {len(products)}")
    print("Products columns:", products.columns.tolist())
    
    # Debug join keys
    print("\nJoin Keys Debug:")
    if 'product_id' in orders.columns:
        print("\nFirst few product_ids in orders:")
        print(orders['product_id'].head())
        print("\nProduct_id type:", orders['product_id'].dtype)
        print("Sample product_id:", orders['product_id'].iloc[0] if len(orders) > 0 else "No orders")
    else:
        print("product_id not found in orders")
        
    if '_id' in products.columns:
        print("\nFirst few _ids in products:")
        print(products['_id'].head())
        print("\n_id type:", products['_id'].dtype)
        print("Sample _id:", products['_id'].iloc[0] if len(products) > 0 else "No products")
    else:
        print("_id not found in products")
    
    # Filter picked up orders
    picked_up_orders = orders[orders['status'] == 'PickedUp']
    print(f"\nPicked up orders: {len(picked_up_orders)}")
    
    if picked_up_orders.empty:
        print("No picked up orders found")
        return
        
    # Convert ObjectId to string if necessary
    if 'product_id' in picked_up_orders.columns:
        if isinstance(picked_up_orders['product_id'].iloc[0], ObjectId):
            picked_up_orders['product_id'] = picked_up_orders['product_id'].astype(str)
            
    if '_id' in products.columns:
        if isinstance(products['_id'].iloc[0], ObjectId):
            products['_id'] = products['_id'].astype(str)
    
    # Debug after conversion
    print("\nAfter type conversion:")
    if 'product_id' in picked_up_orders.columns:
        print("Product_id type:", picked_up_orders['product_id'].dtype)
        print("Sample product_id:", picked_up_orders['product_id'].iloc[0] if len(picked_up_orders) > 0 else "No orders")
        
    if '_id' in products.columns:
        print("_id type:", products['_id'].dtype)
        print("Sample _id:", products['_id'].iloc[0] if len(products) > 0 else "No products")
    
    # Check for matching values
    if 'product_id' in picked_up_orders.columns and '_id' in products.columns:
        matching_values = set(picked_up_orders['product_id']).intersection(set(products['_id']))
        print(f"\nNumber of matching values between product_id and _id: {len(matching_values)}")
        if len(matching_values) > 0:
            print("Sample matching values:", list(matching_values)[:5])
        else:
            print("No matching values found between product_id and _id")
            print("\nSample values from orders['product_id']:", picked_up_orders['product_id'].head().tolist())
            print("Sample values from products['_id']:", products['_id'].head().tolist())
    
    # Attempt merge
    try:
        merged_df = pd.merge(
            picked_up_orders, 
            products,
            left_on="product_id",
            right_on="_id",
            suffixes=("_order", "_product")
        )
        
        print(f"\nMerged records: {len(merged_df)}")
        if merged_df.empty:
            print("No matching records found after merging orders and products")
            return
            
    except KeyError as e:
        print(f"Error during merge: Missing key {str(e)}")
        return
    
    print("\n=== Workmanship Analysis Report ===")
    
    # Check for workmanship column
    if 'workmanship' not in merged_df.columns:
        print("Error: 'workmanship' column not found in merged data")
        return
        
    # Basic Statistics
    print("\n1. Basic Workmanship Statistics:")
    workmanship_stats = merged_df['workmanship'].describe()
    print(workmanship_stats)
    print(f"\nInterpretation: {analyze_workmanship_distribution(merged_df['workmanship'].dropna())}")
    
    # Add materials count if materials column exists
    if 'materials' in merged_df.columns:
        merged_df['number_of_materials'] = merged_df['materials'].apply(len)
    else:
        print("\nWarning: 'materials' column not found")
        merged_df['number_of_materials'] = 0
    
    # Time Analysis
    if 'time_taken' in merged_df.columns:
        print("\n2. Time Efficiency Analysis:")
        valid_data = merged_df.dropna(subset=['time_taken', 'workmanship'])
        if len(valid_data) >= 2:
            print("\nTime Taken vs Workmanship:")
            print(analyze_time_efficiency(valid_data['time_taken'], valid_data['workmanship']))
        else:
            print("Insufficient data for time analysis")
    else:
        print("\nWarning: 'time_taken' column not found")
    
    # Product Complexity Analysis
    print("\n3. Product Complexity Analysis:")
    valid_data = merged_df.dropna(subset=['number_of_materials', 'workmanship'])
    if len(valid_data) >= 2:
        print("\nNumber of Materials vs Workmanship:")
        print(analyze_product_complexity(valid_data['number_of_materials'], valid_data['workmanship']))
    else:
        print("Insufficient data for complexity analysis")
    
    # Product Type Analysis
    if 'type' in merged_df.columns:
        print("\n4. Product Type Analysis:")
        type_workmanship = merged_df.groupby('type')['workmanship'].agg(['mean', 'std', 'count'])
        print("\nWorkmanship by Product Type:")
        print(type_workmanship)
    else:
        print("\nWarning: 'type' column not found")
    
    # Only create visualizations if we have enough data
    if len(merged_df) >= 2:
        # Visualizations
        plt.figure(figsize=(15, 10))
        
        # Workmanship Distribution
        plt.subplot(2, 2, 1)
        sns.histplot(merged_df['workmanship'].dropna(), kde=True)
        plt.title('Distribution of Workmanship Scores')
        plt.xlabel('Workmanship Score')
        
        # Time vs Workmanship
        if 'time_taken' in merged_df.columns:
            plt.subplot(2, 2, 2)
            sns.scatterplot(data=merged_df.dropna(subset=['time_taken', 'workmanship']), 
                          x='time_taken', y='workmanship')
            plt.title('Time Taken vs Workmanship')
            plt.xlabel('Time Taken')
            plt.ylabel('Workmanship Score')
        
        # Materials vs Workmanship
        plt.subplot(2, 2, 3)
        sns.scatterplot(data=merged_df.dropna(subset=['number_of_materials', 'workmanship']), 
                      x='number_of_materials', y='workmanship')
        plt.title('Number of Materials vs Workmanship')
        plt.xlabel('Number of Materials')
        plt.ylabel('Workmanship Score')
        
        # Workmanship by Product Type
        if 'type' in merged_df.columns:
            plt.subplot(2, 2, 4)
            sns.boxplot(data=merged_df.dropna(subset=['type', 'workmanship']), 
                       x='type', y='workmanship')
            plt.title('Workmanship by Product Type')
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.show()
        
        # Correlation Analysis
        print("\n5. Correlation Analysis:")
        correlation_features = ['workmanship', 'time_taken', 'number_of_materials']
        if 'materials_price' in merged_df.columns:
            correlation_features.append('materials_price')
        
        correlation_matrix = merged_df[correlation_features].corr()
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0)
        plt.title('Correlation Matrix of Key Features')
        plt.tight_layout()
        plt.show()
        
        # Time Series Analysis
        if 'finished_order_time' in merged_df.columns:
            print("\n6. Workmanship Trends Over Time:")
            # Apply the custom parser
            merged_df['finished_order_time'] = merged_df['finished_order_time'].apply(parse_mongo_date)

            # Remove any rows where date parsing failed
            valid_dates = merged_df.dropna(subset=['finished_order_time'])

            if len(valid_dates) > 0:
                # Print debug information
                print("Parsed dates:")
                print(valid_dates['finished_order_time'])
                print("\nFull data sample:")
                print(valid_dates)

                # Calculate date range
                date_range = (valid_dates['finished_order_time'].max() - 
                             valid_dates['finished_order_time'].min()).days

                print(f"\nTime range: {valid_dates['finished_order_time'].min()} to {valid_dates['finished_order_time'].max()}")
                print(f"Date range in days: {date_range}")

                plt.figure(figsize=(15, 7))

                # Create scatter plot for individual data points
                plt.scatter(valid_dates['finished_order_time'], 
                           valid_dates['workmanship'],
                           color='blue',
                           alpha=0.6,
                           s=100,
                           label='Individual Orders')

                # If we have multiple points per day, show daily average line
                daily_avg = valid_dates.groupby('finished_order_time')['workmanship'].mean()
                if len(daily_avg) > 1:
                    daily_avg.plot(color='red', linewidth=2, label='Daily Average')

                # Customize the plot
                plt.title('Workmanship Scores Over Time', pad=20, size=14)
                plt.xlabel('Date', size=12)
                plt.ylabel('Workmanship Score', size=12)

                # Format x-axis
                plt.gca().xaxis.set_major_locator(plt.AutoLocator())
                plt.gca().xaxis.set_major_formatter(plt.FixedFormatter('%Y-%m-%d'))

                # Add grid for better readability
                plt.grid(True, linestyle='--', alpha=0.7)

                # Rotate and align the tick labels so they look better
                plt.gcf().autofmt_xdate()

                # Add legend
                plt.legend()

                # Add some padding to the y-axis
                y_min = valid_dates['workmanship'].min()
                y_max = valid_dates['workmanship'].max()
                y_padding = (y_max - y_min) * 0.1
                plt.ylim(y_min - y_padding, y_max + y_padding)

                # Ensure the x-axis shows all data with some padding
                x_min = valid_dates['finished_order_time'].min()
                x_max = valid_dates['finished_order_time'].max()
                plt.xlim(x_min - pd.Timedelta(days=1), x_max + pd.Timedelta(days=1))

                plt.tight_layout()
                plt.show()

                # Print additional statistics
                print("\nWorkmanship Statistics by Date:")
                daily_stats = valid_dates.groupby('finished_order_time').agg({
                    'workmanship': ['count', 'mean', 'std']
                }).round(2)
                print(daily_stats)
            else:
                print("No valid dates found after parsing")
        else:
            print("\nWarning: 'finished_order_time' column not found")

def main():
    connection_string = "mongodb://localhost:27017/TailoringDb"
    mongodb_service = MongoDBService(connection_string=connection_string)
    
    print("Analyzing workmanship data...")
    analyze_workmanship_data(mongodb_service)
    
    if 'mongodb_service' in locals():
        mongodb_service.client.close()

if __name__ == "__main__":
    main()