"""
QuickBooks Customer Management Examples

This file demonstrates how to use the QuickBooks Customer management system.
"""

from .accounts import (
    Customer, EmailAddr, TelephoneNumber, PhysicalAddr, 
    QuickBooksCustomerManager, create_sample_customer
)
from .base import QuickBooksAuth


def example_create_customer_from_json():
    """Example: Create a Customer from the provided JSON structure"""
    
    # Sample data matching the provided JSON
    customer_data = {
        "DisplayName": "Bill's Windsurf Shop",
        "CompanyName": "Bill's Windsurf Shop", 
        "GivenName": "Bill",
        "FamilyName": "Lucchini",
        "PrimaryEmailAddr": {"Address": "Surf@Intuit.com"},
        "PrimaryPhone": {"FreeFormNumber": "(415) 444-6538"},
        "BillAddr": {
            "City": "Half Moon Bay",
            "Line1": "12 Ocean Dr.",
            "PostalCode": "94213",
            "CountrySubDivisionCode": "CA",
            "Id": "3"
        },
        "Balance": 85.0,
        "BalanceWithJobs": 85.0,
        "Taxable": False,
        "PrintOnCheckName": "Bill's Windsurf Shop",
        "PreferredDeliveryMethod": "Print",
        "Id": "2",
        "SyncToken": "0"
    }
    
    # Create Customer instance
    customer = Customer(**customer_data)
    return customer


def example_customer_manager_usage():
    """Example: Using the QuickBooksCustomerManager"""
    
    # Initialize QuickBooks authentication
    auth = QuickBooksAuth(
        client_id="your_client_id",
        client_secret="your_client_secret",
        redirect_uri="http://localhost:8000/finance/quickbooks/callback/",
        environment="sandbox"  # or "production"
    )
    
    # Set authentication tokens (these would come from OAuth flow)
    auth.access_token = "your_access_token"
    auth.refresh_token = "your_refresh_token"
    auth.realm_id = "your_company_id"
    
    # Create customer manager
    customer_manager = QuickBooksCustomerManager(auth)
    
    return customer_manager


async def example_full_customer_workflow():
    """Example: Complete customer management workflow"""
    
    # Get customer manager
    manager = example_customer_manager_usage()
    
    try:
        # 1. Create a new customer
        new_customer = Customer(
            DisplayName="John's Coffee Shop",
            CompanyName="John's Coffee Shop",
            GivenName="John",
            FamilyName="Smith",
            PrimaryEmailAddr=EmailAddr(Address="john@coffeeshop.com"),
            PrimaryPhone=TelephoneNumber(FreeFormNumber="(555) 123-4567"),
            BillAddr=PhysicalAddr(
                Line1="456 Coffee St",
                City="Seattle",
                CountrySubDivisionCode="WA",
                PostalCode="98101"
            )
        )
        
        created_customer = manager.create_customer(new_customer)
        print(f"Created customer: {created_customer.Id}")
        
        # 2. Retrieve the customer
        retrieved_customer = manager.get_customer(created_customer.Id)
        print(f"Retrieved customer: {retrieved_customer.DisplayName}")
        
        # 3. Update the customer
        retrieved_customer.PrimaryEmailAddr.Address = "newemail@coffeeshop.com"
        updated_customer = manager.update_customer(retrieved_customer)
        print(f"Updated customer email: {updated_customer.PrimaryEmailAddr.Address}")
        
        # 4. List all customers
        customers = manager.list_customers(max_results=10)
        print(f"Found {len(customers)} customers")
        
        # 5. Search for customers
        search_results = manager.search_customers("Coffee", max_results=5)
        print(f"Found {len(search_results)} customers matching 'Coffee'")
        
        # 6. Get customer balance
        balance_info = manager.get_customer_balance(created_customer.Id)
        print(f"Customer balance: ${balance_info['balance']}")
        
        # 7. Deactivate the customer (soft delete)
        success = manager.delete_customer(updated_customer)
        print(f"Customer deactivated: {success}")
        
    except Exception as e:
        print(f"Error in customer workflow: {e}")


def example_integration_with_django():
    """Example: Integration with Django QuickBooks service"""
    
    # This would typically be called from your Django QuickBooks service
    def create_customer_from_student(student_data):
        """Convert student data to QuickBooks customer"""
        
        customer = Customer(
            DisplayName=f"{student_data['first_name']} {student_data['last_name']}",
            GivenName=student_data['first_name'],
            FamilyName=student_data['last_name'],
            PrimaryEmailAddr=EmailAddr(Address=student_data['email']) if student_data.get('email') else None,
            BillAddr=PhysicalAddr(
                Line1=student_data.get('address_line1'),
                City=student_data.get('city'),
                CountrySubDivisionCode=student_data.get('state'),
                PostalCode=student_data.get('postal_code')
            ) if student_data.get('address_line1') else None
        )
        
        return customer
    
    # Example student data
    student = {
        'first_name': 'Alice',
        'last_name': 'Johnson', 
        'email': 'alice@example.com',
        'address_line1': '123 Student Ave',
        'city': 'Studentville',
        'state': 'CA',
        'postal_code': '90210'
    }
    
    customer = create_customer_from_student(student)
    return customer


if __name__ == "__main__":
    # Run examples
    print("QuickBooks Customer Management Examples")
    print("=" * 50)
    
    # Example 1: Create from JSON
    print("\n1. Creating customer from JSON data...")
    customer = example_create_customer_from_json()
    print(f"   Customer: {customer.DisplayName} (Balance: ${customer.Balance})")
    
    # Example 2: Sample customer
    print("\n2. Creating sample customer...")
    sample = create_sample_customer()
    print(f"   Sample: {sample.DisplayName}")
    
    # Example 3: Django integration
    print("\n3. Django integration example...")
    student_customer = example_integration_with_django()
    print(f"   Student Customer: {student_customer.DisplayName}")
    
    print("\n✅ All examples completed successfully!")
    print("\n💡 To use with real QuickBooks API:")
    print("   1. Set up proper OAuth credentials")
    print("   2. Complete OAuth flow to get access tokens")
    print("   3. Use QuickBooksCustomerManager for CRUD operations")