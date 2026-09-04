CATALOG = (
    {
        "slug": "clean-bathroom",
        "name": "Clean bathroom",
        "description": "Clean the bathroom surfaces and fixtures.",
        "category": "cleaning",
    },
    {
        "slug": "vacuum-floors",
        "name": "Vacuum floors",
        "description": "Vacuum the household floors.",
        "category": "cleaning",
    },
    {
        "slug": "wash-clothes",
        "name": "Wash clothes",
        "description": "Wash a household load of clothes.",
        "category": "laundry",
    },
    {
        "slug": "fold-clothes",
        "name": "Fold clothes",
        "description": "Fold and put away clean clothes.",
        "category": "laundry",
    },
    {
        "slug": "wash-dishes",
        "name": "Wash dishes",
        "description": "Wash dishes and leave the kitchen ready to use.",
        "category": "kitchen",
    },
    {
        "slug": "empty-dishwasher",
        "name": "Empty dishwasher",
        "description": "Empty the dishwasher and put items away.",
        "category": "kitchen",
    },
    {
        "slug": "grocery-shopping",
        "name": "Grocery shopping",
        "description": "Buy the household groceries.",
        "category": "shopping",
    },
    {
        "slug": "buy-household-supplies",
        "name": "Buy household supplies",
        "description": "Restock essential household supplies.",
        "category": "shopping",
    },
    {
        "slug": "take-out-trash",
        "name": "Take out trash",
        "description": "Take household trash to the collection point.",
        "category": "maintenance",
    },
    {
        "slug": "water-plants",
        "name": "Water plants",
        "description": "Water the household plants.",
        "category": "maintenance",
    },
)

CATALOG_BY_SLUG = {template["slug"]: template for template in CATALOG}
