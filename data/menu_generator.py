import json
import random

def generate_menu():
    categories = ["Starters", "Main Course", "Desserts", "Beverages"]
    
    starters = [
        {"name": "Spicy Chicken Wings", "price": 12.99, "desc": "Crispy wings tossed in spicy buffalo sauce", "spice": "High", "allergens": ["Gluten", "Dairy"]},
        {"name": "Bruschetta", "price": 8.50, "desc": "Toasted bread with fresh tomatoes and basil", "spice": "None", "allergens": ["Gluten"]},
        {"name": "Truffle Fries", "price": 9.00, "desc": "Crispy fries with truffle oil and parmesan", "spice": "Low", "allergens": ["Dairy"]},
    ]
    
    mains = [
        {"name": "Classic Burger", "price": 15.99, "desc": "Juicy beef patty with lettuce, tomato, and cheese", "spice": "Medium", "allergens": ["Gluten", "Dairy"]},
        {"name": "Vegan Buddha Bowl", "price": 14.50, "desc": "Quinoa, roasted veggies, avocado, and tahini dressing", "spice": "Low", "allergens": ["Sesame"]},
        {"name": "Grilled Salmon", "price": 22.00, "desc": "Fresh salmon with asparagus and lemon butter sauce", "spice": "None", "allergens": ["Fish", "Dairy"]},
        {"name": "Butter Chicken", "price": 18.00, "desc": "Tender chicken simmered in a creamy tomato sauce", "spice": "Medium", "allergens": ["Dairy", "Nuts"]},
    ]
    
    desserts = [
        {"name": "Chocolate Lava Cake", "price": 9.50, "desc": "Warm chocolate cake with a gooey center", "spice": "None", "allergens": ["Gluten", "Dairy", "Eggs"]},
        {"name": "Cheesecake", "price": 8.00, "desc": "Classic New York style cheesecake", "spice": "None", "allergens": ["Dairy", "Gluten", "Eggs"]},
    ]
    
    beverages = [
        {"name": "Lemonade", "price": 4.00, "desc": "Freshly squeezed lemonade", "spice": "None", "allergens": []},
        {"name": "Iced Coffee", "price": 5.00, "desc": "Cold brew coffee with milk", "spice": "None", "allergens": ["Dairy"]},
        {"name": "Mango Lassi", "price": 6.00, "desc": "Yogurt based mango drink", "spice": "None", "allergens": ["Dairy"]},
    ]

    menu = {
        "restaurant_name": "The Future Dinesh",
        "currency": "USD",
        "categories": {
            "Starters": starters,
            "Main Course": mains,
            "Desserts": desserts,
            "Beverages": beverages
        }
    }
    
    with open("data/menu.json", "w") as f:
        json.dump(menu, f, indent=4)
    print("Menu generated in data/menu.json")

if __name__ == "__main__":
    generate_menu()
