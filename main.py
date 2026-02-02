from dotenv import load_dotenv
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mysql.connector import connect, Error
from pydantic import BaseModel
import uvicorn
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Fetch DB credentials from .env file
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
DBNAME = os.getenv("DBNAME")

app = FastAPI()

print(USER,PASSWORD,HOST,PORT,DBNAME)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (change this for security)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

# MySQL Connection Details
db_config = {
    "host": HOST,
    "user": USER,
    "password": PASSWORD,
    "database": "retail_management"
}
print(db_config)
# Models
class User(BaseModel):
    username: str
    email: str
    password: str

class Login(BaseModel):
    email: str
    password: str

class Product(BaseModel):
    product_name: str
    category: str
    price: float
    user_id: int  # Foreign key to users table

class Stock(BaseModel):
    product_id: int
    stock_quantity: int
    expiry_date: str
    user_id: int  # Foreign key to users table

class Sale(BaseModel):
    product_id: int
    quantity_sold: int
    user_id: int  # Foreign key to users table

# Helper function to execute queries
def execute_query(query, params=None):
    try:
        with connect(**db_config) as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(query, params)
                if cursor.description:  # SELECT query
                    return cursor.fetchall()
                connection.commit()  # For INSERT, UPDATE, DELETE
                return None
    except Error as e:
        return {"error": str(e)}

# Sign up endpoint
@app.post("/signup/")
def signup(user: User):
    # Check if the user already exists
    check_query = "SELECT user_id FROM users WHERE email = %s"
    existing_user = execute_query(check_query, (user.email,))
    print(existing_user)
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Insert new user
    query = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
    params = (user.username, user.email, user.password)
    result = execute_query(query, params)
    
    if result is None:
        return {"message": "User registered successfully"}
    
    return result  # Return error if any

# Login endpoint
@app.post("/login/")
def login(login_data: Login):
    query = "SELECT user_id, email, password FROM users WHERE email = %s AND password = %s"
    user = execute_query(query, (login_data.email, login_data.password))
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    return {"message": "Login successful", "user_id": user[0]["user_id"]}

# Add product
@app.post("/products/")
def add_product(product: Product):
    query = "INSERT INTO products (product_name, category, price, user_id) VALUES (%s, %s, %s, %s)"
    params = (product.product_name, product.category, product.price, product.user_id)
    result = execute_query(query, params)
    
    if result is None:
        return {"message": "Product added successfully"}
    
    return result  # Return error if any

# Get all products
@app.get("/products/")
def get_products(user_id: int):
    query = "SELECT * FROM products WHERE user_id = %s"
    products = execute_query(query, (user_id,))
    
    if isinstance(products, list):  
        return products
    
    return {"error": "Error fetching products"}

# Add stock
@app.post("/stocks/")
def add_stock(stock: Stock):
    query = "INSERT INTO stocks (product_id, stock_quantity, expiry_date, user_id) VALUES (%s, %s, %s, %s)"
    params = (stock.product_id, stock.stock_quantity, stock.expiry_date, stock.user_id)
    result = execute_query(query, params)
    
    if result is None:
        return {"message": "Stock added successfully"}
    
    return result  # Return error if any

# Get all stocks for a user
@app.get("/stocks/")
def get_stocks(user_id: int):
    query = """
        SELECT s.stock_id, p.product_name, s.stock_quantity, s.expiry_date
        FROM stocks s
        JOIN products p ON s.product_id = p.product_id
        WHERE s.user_id = %s
    """
    stocks = execute_query(query, (user_id,))
    
    if isinstance(stocks, list):
        return stocks
    
    return {"error": "Error fetching stocks"}

# Add sale
@app.post("/sales/")
def add_sale(sale: Sale):
    # Check stock availability
    stock_check_query = "SELECT stock_quantity FROM stocks WHERE product_id = %s"
    stock = execute_query(stock_check_query, (sale.product_id,))
    
    if not stock or stock[0]['stock_quantity'] < sale.quantity_sold:
        raise HTTPException(status_code=400, detail="Insufficient stock available")

    # Insert sale record
    query = "INSERT INTO sales (product_id, quantity_sold, user_id) VALUES (%s, %s, %s)"
    params = (sale.product_id, sale.quantity_sold, sale.user_id)
    execute_query(query, params)

    # Update stock quantity
    update_query = "UPDATE stocks SET stock_quantity = stock_quantity - %s WHERE product_id = %s"
    update_params = (sale.quantity_sold, sale.product_id)
    execute_query(update_query, update_params)

    return {"message": "Sale added and stock updated successfully"}


# Get all sales
@app.get("/sales/")
def get_sales(user_id: int):
    query = """
        SELECT s.sale_id, p.product_name, s.quantity_sold, s.sale_date
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        WHERE s.user_id = %s
    """
    sales = execute_query(query, (user_id,))
    
    if isinstance(sales, list):
        return sales
    
    return {"error": "Error fetching sales"}

# Get expiring stocks
@app.get("/stocks/expiring/")
def get_expiring_stocks(user_id: int, days: int = 7):
    expiry_threshold = datetime.now() + timedelta(days=days)
    query = """
        SELECT s.stock_id, p.product_name, s.stock_quantity, s.expiry_date
        FROM stocks s
        JOIN products p ON s.product_id = p.product_id
        WHERE s.expiry_date <= %s AND s.user_id = %s
    """
    params = (expiry_threshold.strftime('%Y-%m-%d'), user_id)
    expiring_stocks = execute_query(query, params)
    
    return expiring_stocks

@app.delete("/products/{product_id}")
def delete_product(product_id: int):
    # Check if product exists
    check_product_query = "SELECT product_id FROM products WHERE product_id = %s"
    product = execute_query(check_product_query, (product_id,))
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Delete related stock entries first
    delete_stock_query = "DELETE FROM stocks WHERE product_id = %s"
    execute_query(delete_stock_query, (product_id,))

    # Delete the product
    delete_product_query = "DELETE FROM products WHERE product_id = %s"
    execute_query(delete_product_query, (product_id,))

    return {"message": "Product and associated stocks deleted successfully"}

@app.delete("/stocks/")
def remove_stock(stock_id: int, quantity: int, user_id: int):
    print(stock_id,quantity,user_id);
    # Check current stock quantity for the specific user
    check_stock_query = "SELECT stock_quantity FROM stocks WHERE stock_id = %s AND user_id = %s"
    stock = execute_query(check_stock_query, (stock_id, user_id))

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found for this product and user")

    current_stock = stock[0]['stock_quantity']

    if current_stock < quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available to remove")

    if current_stock == quantity:
        # If removing all stock, delete the stock entry for this user
        delete_stock_query = "DELETE FROM stocks WHERE stock_id = %s AND user_id = %s"
        execute_query(delete_stock_query, (stock_id, user_id))
        return {"message": "Stock completely removed"}

    # Otherwise, update the stock quantity for this user
    update_stock_query = "UPDATE stocks SET stock_quantity = stock_quantity - %s WHERE stock_id = %s AND user_id = %s"
    execute_query(update_stock_query, (quantity, stock_id, user_id))
    
    return {"message": f"Stock reduced by {quantity}. Remaining stock: {current_stock - quantity}"}

# Run the FastAPI server
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)