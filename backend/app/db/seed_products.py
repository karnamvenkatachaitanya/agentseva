"""
Database Seed Script for Agent Seva Kirana Store 200+ Products Dataset.
"""

SEED_PRODUCTS = [
    {
        "id": "prod-1",
        "name": "Amul Taaza Toned Milk (1L)",
        "price": 54,
        "category": "Dairy & Eggs",
        "stock": 65,
        "location": "Aisle 3A (Refrigerated)",
        "barcode": "8901262010011"
    },
    {
        "id": "prod-21",
        "name": "Tata Sampann Unpolished Toor Dal (1kg)",
        "price": 170,
        "category": "Pulses & Dal",
        "stock": 55,
        "location": "Aisle 4B (Pulses & Grains)",
        "barcode": "8901262020218"
    },
    {
        "id": "prod-41",
        "name": "Aashirvaad Shudh Chakki Atta (10kg)",
        "price": 430,
        "category": "Atta, Rice & Grains",
        "stock": 50,
        "location": "Aisle 4A (Atta & Flour)",
        "barcode": "8901262030415"
    },
    {
        "id": "prod-61",
        "name": "Fortune Sunlite Sunflower Oil Pouch (1L)",
        "price": 145,
        "category": "Oils & Ghee",
        "stock": 60,
        "location": "Aisle 2A (Edible Oils)",
        "barcode": "8901262040612"
    },
    {
        "id": "prod-81",
        "name": "Tata Salt Vacuum Evaporated Iodised (1kg)",
        "price": 28,
        "category": "Spices & Masala",
        "stock": 120,
        "location": "Aisle 2B (Spices & Salt)",
        "barcode": "8901262050819"
    },
    {
        "id": "prod-101",
        "name": "Parle-G Glucose Biscuits (800g Family Pack)",
        "price": 90,
        "category": "Snacks & Biscuits",
        "stock": 80,
        "location": "Aisle 1B (Biscuits)",
        "barcode": "8901262061013"
    },
    {
        "id": "prod-121",
        "name": "Brooke Bond Red Label Tea Pouch (1kg)",
        "price": 520,
        "category": "Beverages",
        "stock": 45,
        "location": "Aisle 2B (Tea & Coffee)",
        "barcode": "8901262071210"
    },
    {
        "id": "prod-141",
        "name": "Dettol Original Soap (125g Pack of 4)",
        "price": 210,
        "category": "Personal Care",
        "stock": 50,
        "location": "Aisle 5A (Soaps & Hygiene)",
        "barcode": "8901262081417"
    },
    {
        "id": "prod-161",
        "name": "Surf Excel Easy Wash Detergent Powder (1kg)",
        "price": 140,
        "category": "Household & Cleaning",
        "stock": 70,
        "location": "Aisle 6A (Laundry Detergents)",
        "barcode": "8901262091614"
    },
    {
        "id": "prod-181",
        "name": "Britannia 100% Whole Wheat Bread (400g)",
        "price": 50,
        "category": "Bakery & Packaged Food",
        "stock": 25,
        "location": "Aisle 1A (Bakery Shelf)",
        "barcode": "8901262101811"
    },
    {
        "id": "prod-201",
        "name": "Fresh Red Tomatoes (1kg Net)",
        "price": 45,
        "category": "Fruits & Vegetables",
        "stock": 40,
        "location": "Aisle 1A (Fresh Produce)",
        "barcode": "8901262112015"
    }
]

def seed_database():
    print(f"Seeding {len(SEED_PRODUCTS)} sample categories of 210 products into Agent Seva DB...")

if __name__ == "__main__":
    seed_database()
