import json
import requests
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, validator

from .base import QuickBooksAuth, AuthClientError

logger = logging.getLogger(__name__)


def _extract_intuit_tid(response: "requests.Response") -> Optional[str]:
    """Pull Intuit's per-request transaction id out of the response headers.

    Required by Intuit support to investigate any API issue - always log it,
    on both success and failure, so it's never missing when someone actually
    needs to file a ticket. Header name/casing per Intuit's docs is
    ``intuit_tid``; check a couple of plausible variants defensively since
    ``requests`` header lookups are case- but not separator-insensitive.
    """
    if response is None:
        return None
    return (
        response.headers.get("intuit_tid")
        or response.headers.get("intuit-tid")
        or response.headers.get("Intuit-T-ID")
    )


class EmailAddr(BaseModel):
    Address: str


class PhysicalAddr(BaseModel):
    Id: Optional[str] = None
    Line1: Optional[str] = None
    Line2: Optional[str] = None
    Line3: Optional[str] = None
    Line4: Optional[str] = None
    Line5: Optional[str] = None
    City: Optional[str] = None
    Country: Optional[str] = None
    CountrySubDivisionCode: Optional[str] = None
    PostalCode: Optional[str] = None
    Lat: Optional[str] = None
    Long: Optional[str] = None


class TelephoneNumber(BaseModel):
    FreeFormNumber: str


class MetaData(BaseModel):
    CreateTime: Optional[str] = None
    LastUpdatedTime: Optional[str] = None


class Customer(BaseModel):
    Id: Optional[str] = None
    SyncToken: str = "0"
    domain: str = "QBO"
    sparse: bool = False

    DisplayName: str
    Name: Optional[str] = None
    CompanyName: Optional[str] = None
    GivenName: Optional[str] = None
    MiddleName: Optional[str] = None
    FamilyName: Optional[str] = None
    Suffix: Optional[str] = None
    FullyQualifiedName: Optional[str] = None
    PrintOnCheckName: Optional[str] = None

    PrimaryEmailAddr: Optional[EmailAddr] = None
    PrimaryPhone: Optional[TelephoneNumber] = None
    Mobile: Optional[TelephoneNumber] = None
    Fax: Optional[TelephoneNumber] = None
    WebAddr: Optional[str] = None

    BillAddr: Optional[PhysicalAddr] = None
    ShipAddr: Optional[PhysicalAddr] = None

    Active: bool = True
    Taxable: bool = True
    Job: bool = False
    BillWithParent: bool = False
    ParentRef: Optional[Dict[str, str]] = None
    Level: int = 0

    Balance: float = 0.0
    BalanceWithJobs: float = 0.0
    CurrencyRef: Optional[Dict[str, str]] = None
    PreferredDeliveryMethod: str = "Print"
    ResaleNum: Optional[str] = None

    SalesTermRef: Optional[Dict[str, str]] = None
    PaymentMethodRef: Optional[Dict[str, str]] = None
    PriceLevelRef: Optional[Dict[str, str]] = None
    TaxCodeRef: Optional[Dict[str, str]] = None

    MetaData: Optional[Dict[str, Any]] = None

    @validator("DisplayName")
    def display_name_required(cls, v):
        if not v or not v.strip():
            raise ValueError("DisplayName is required")
        return v.strip()

    @validator("Balance", "BalanceWithJobs")
    def validate_balance(cls, v):
        if v < 0:
            logger.warning(f"Negative balance detected: {v}")
        return v


class QuickBooksCustomerManager:
    def __init__(self, auth: QuickBooksAuth):
        self.auth = auth
        self.base_url = auth.discovery_url
        # Transaction id of the most recent Intuit API call (success or
        # failure) - callers can read this right after _make_request returns
        # to attach it to their own sync-log entries.
        self.last_intuit_tid: Optional[str] = None

    def _get_headers(self) -> Dict[str, str]:
        return self.auth.get_auth_headers()

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v3/company/{self.auth.realm_id}/{endpoint}"
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                headers["Content-Type"] = "application/json"
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            self.last_intuit_tid = _extract_intuit_tid(response)
            logger.debug(f"QuickBooks API call {method} {endpoint} succeeded (intuit_tid={self.last_intuit_tid})")
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            self.last_intuit_tid = _extract_intuit_tid(e.response)
            # Get detailed error response from QuickBooks
            error_details = ""
            try:
                error_response = e.response.json()
                error_details = f" - Response: {error_response}"
            except:
                error_details = f" - Text: {e.response.text}"

            error_msg = (
                f"QuickBooks API request failed: {e.response.status_code}{error_details} "
                f"- Request data: {data} - intuit_tid: {self.last_intuit_tid}"
            )
            logger.error(error_msg)
            raise AuthClientError(error_msg)
        except requests.RequestException as e:
            logger.error(f"QuickBooks API request failed: {str(e)}")
            raise AuthClientError(f"QuickBooks API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse QuickBooks API response: {str(e)}")
            raise AuthClientError(f"Invalid JSON response from QuickBooks API")

    def create_customer(self, customer: Customer) -> Customer:
        try:
            customer_data = {"DisplayName": customer.DisplayName}
            if customer.GivenName and customer.GivenName.strip():
                customer_data["GivenName"] = customer.GivenName.strip()
            if customer.FamilyName and customer.FamilyName.strip():
                customer_data["FamilyName"] = customer.FamilyName.strip()
            if hasattr(customer, 'MiddleName') and customer.MiddleName:
                customer_data["MiddleName"] = customer.MiddleName
            if hasattr(customer, 'PrimaryEmailAddr') and customer.PrimaryEmailAddr:
                customer_data['PrimaryEmailAddr'] = customer.PrimaryEmailAddr.dict(exclude_none=True)
            if hasattr(customer, 'PrimaryPhone') and customer.PrimaryPhone:
                customer_data['PrimaryPhone'] = customer.PrimaryPhone.dict(exclude_none=True)
            if hasattr(customer, 'BillAddr') and customer.BillAddr:
                customer_data['BillAddr'] = customer.BillAddr.dict(exclude_none=True)

            logger.info(f"Creating QuickBooks customer: {customer.DisplayName}")
            response = self._make_request("POST", "customer", customer_data)

            if "QueryResponse" in response and response["QueryResponse"].get("Customer"):
                return Customer(**response["QueryResponse"]["Customer"][0])
            elif "Customer" in response:
                return Customer(**response["Customer"])
            else:
                raise AuthClientError("Unexpected response format from QuickBooks API")

        except requests.exceptions.HTTPError as e:
            try:
                error_response = e.response.json()
            except Exception:
                error_response = {}

            # Error code 6240 = Duplicate Name Exists — find and return the existing customer
            fault = error_response.get('Fault', {})
            errors = fault.get('Error', [])
            if e.response.status_code == 400 and any(err.get('code') == '6240' for err in errors):
                logger.warning(
                    f"Duplicate DisplayName '{customer.DisplayName}' in QuickBooks — fetching existing customer"
                )
                existing = self.search_customers(customer.DisplayName, max_results=1)
                if existing:
                    logger.info(f"Found existing customer ID {existing[0].Id} for '{customer.DisplayName}'")
                    return existing[0]
                raise AuthClientError(
                    f"Duplicate name '{customer.DisplayName}' exists in QuickBooks but could not be retrieved"
                )

            error_msg = f"QuickBooks API request failed: {e.response.status_code} - Response: {error_response} - Request data: {customer_data}"
            logger.error(error_msg)
            raise AuthClientError(error_msg)

        except Exception as e:
            error_msg = f"Failed to create customer: {str(e)}"
            logger.error(error_msg)
            raise AuthClientError(error_msg)

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        try:
            logger.info(f"Retrieving customer ID: {customer_id}")
            response = self._make_request("GET", f"customer/{customer_id}")

            if "QueryResponse" in response and response["QueryResponse"]:
                customer_data = response["QueryResponse"]["Customer"][0]
                return Customer(**customer_data)

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve customer {customer_id}: {str(e)}")
            raise AuthClientError(f"Failed to retrieve customer: {str(e)}")

    def update_customer(self, customer: Customer) -> Customer:
        try:
            if not customer.Id:
                raise ValueError("Customer ID is required for updates")

            customer_data = customer.dict(exclude_none=True)

            logger.info(f"Updating customer ID: {customer.Id}")
            response = self._make_request(
                "POST", "customer", {"Customer": customer_data}
            )

            if "QueryResponse" in response:
                updated_data = response["QueryResponse"]["Customer"][0]
            elif "Customer" in response:
                updated_data = response["Customer"]
            else:
                raise AuthClientError("Unexpected response format from QuickBooks API")

            logger.info(f"Successfully updated customer ID: {customer.Id}")
            return Customer(**updated_data)

        except Exception as e:
            logger.error(f"Failed to update customer: {str(e)}")
            raise AuthClientError(f"Failed to update customer: {str(e)}")

    def delete_customer(self, customer: Customer) -> bool:
        try:
            if not customer.Id:
                raise ValueError("Customer ID is required for deletion")

            customer.Active = False
            self.update_customer(customer)

            logger.info(f"Successfully deactivated customer ID: {customer.Id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete customer: {str(e)}")
            raise AuthClientError(f"Failed to delete customer: {str(e)}")

    def list_customers(
        self, active_only: bool = True, max_results: int = 20
    ) -> List[Customer]:
        try:
            query = "SELECT * FROM Customer"
            if active_only:
                query += " WHERE Active = true"
            query += f" MAXRESULTS {max_results}"

            logger.info(f"Querying customers: {query}")
            from urllib.parse import quote_plus
            encoded_query = quote_plus(query)
            response = self._make_request("GET", f"query?query={encoded_query}")

            customers = []
            if "QueryResponse" in response and "Customer" in response["QueryResponse"]:
                for customer_data in response["QueryResponse"]["Customer"]:
                    customers.append(Customer(**customer_data))

            logger.info(f"Retrieved {len(customers)} customers")
            return customers

        except Exception as e:
            logger.error(f"Failed to list customers: {str(e)}")
            raise AuthClientError(f"Failed to list customers: {str(e)}")

    def list_all_customers(self, active_only: bool = True, page_size: int = 1000) -> List[Customer]:
        """Every customer, paging through STARTPOSITION/MAXRESULTS.

        ``list_customers`` caps at a single page (default 20) - use this for the
        reconciliation/linking pass, which must see the whole customer list.
        """
        from urllib.parse import quote_plus

        page_size = max(1, min(page_size, 1000))
        where = " WHERE Active = true" if active_only else ""
        customers: List[Customer] = []
        start = 1
        while True:
            query = (
                f"SELECT * FROM Customer{where} "
                f"STARTPOSITION {start} MAXRESULTS {page_size}"
            )
            response = self._make_request("GET", f"query?query={quote_plus(query)}")
            rows = []
            if "QueryResponse" in response and "Customer" in response["QueryResponse"]:
                rows = response["QueryResponse"]["Customer"]
            for row in rows:
                try:
                    customers.append(Customer(**row))
                except Exception as e:
                    logger.warning(f"Skipping unparseable Customer {row.get('Id')}: {e}")
            if len(rows) < page_size:
                break
            start += page_size
        logger.info(f"Retrieved {len(customers)} customers from QuickBooks")
        return customers

    def search_customers(self, search_term: str, max_results: int = 20) -> List[Customer]:
        try:
            # First try with just the name part (before parentheses) to avoid query issues
            clean_search_term = search_term.split(" (")[0] if " (" in search_term else search_term
            # Escape single quotes for SQL
            escaped_search_term = clean_search_term.replace("'", "''")
            query = f"SELECT * FROM Customer WHERE DisplayName LIKE '%{escaped_search_term}%' OR CompanyName LIKE '%{escaped_search_term}%' MAXRESULTS {max_results}"

            logger.info(f"Searching customers with query: {query}")
            # Properly URL encode the entire query parameter
            from urllib.parse import quote_plus
            encoded_query = quote_plus(query)
            response = self._make_request("GET", f"query?query={encoded_query}")

            customers = []
            if "QueryResponse" in response and "Customer" in response["QueryResponse"]:
                for customer_data in response["QueryResponse"]["Customer"]:
                    customers.append(Customer(**customer_data))

            logger.info(f"Found {len(customers)} customers matching '{search_term}'")
            return customers

        except requests.exceptions.HTTPError as e:
            error_msg = f"QuickBooks API request failed: {e.response.status_code} - {e.response.text} - Query: {query}"
            logger.error(error_msg)
            if e.response.status_code == 400:
                logger.warning(
                    f"Query failed, attempting fallback without special characters"
                )
                # Fallback: Retry without parentheses
                plain_search_term = search_term.split(" (")[
                    0
                ]  # e.g., "Walid Nassar" from "Walid Nassar (GRA25001)"
                escaped_plain_term = plain_search_term.replace("'", "''")
                query = f"SELECT * FROM Customer WHERE DisplayName LIKE '%{escaped_plain_term}%' OR CompanyName LIKE '%{escaped_plain_term}%' MAXRESULTS {max_results}"
                try:
                    logger.info(f"Fallback query: {query}")
                    from urllib.parse import quote_plus
                    encoded_fallback_query = quote_plus(query)
                    response = self._make_request("GET", f"query?query={encoded_fallback_query}")
                    customers = []
                    if (
                        "QueryResponse" in response
                        and "Customer" in response["QueryResponse"]
                    ):
                        for customer_data in response["QueryResponse"]["Customer"]:
                            customers.append(Customer(**customer_data))
                    logger.info(
                        f"Found {len(customers)} customers in fallback query for '{plain_search_term}'"
                    )
                    return customers
                except requests.exceptions.RequestException as fallback_e:
                    error_msg = f"Fallback query failed: {fallback_e.response.status_code} - {fallback_e.response.text} - Query: {query}"
                    logger.error(error_msg)
                    raise AuthClientError(error_msg)
            raise AuthClientError(error_msg)
        except Exception as e:
            error_msg = f"Failed to search customers: {str(e)}"
            logger.error(error_msg)
            raise AuthClientError(error_msg)

    def get_customer_balance(self, customer_id: str) -> Dict[str, float]:
        try:
            customer = self.get_customer(customer_id)
            if not customer:
                raise ValueError(f"Customer with ID {customer_id} not found")

            return {
                "balance": customer.Balance,
                "balance_with_jobs": customer.BalanceWithJobs,
            }

        except Exception as e:
            logger.error(f"Failed to get customer balance: {str(e)}")
            raise AuthClientError(f"Failed to get customer balance: {str(e)}")


def create_customer_from_dict(customer_data: Dict[str, Any]) -> Customer:
    return Customer(**customer_data)


def create_sample_customer() -> Customer:
    return Customer(
        DisplayName="Sample Customer",
        CompanyName="Sample Company Inc.",
        GivenName="John",
        FamilyName="Doe",
        PrimaryEmailAddr=EmailAddr(Address="john@samplecompany.com"),
        PrimaryPhone=TelephoneNumber(FreeFormNumber="(555) 123-4567"),
        BillAddr=PhysicalAddr(
            Line1="123 Main St",
            City="Anytown",
            CountrySubDivisionCode="CA",
            PostalCode="12345",
        ),
        Taxable=True,
        Active=True,
    )


class Line(BaseModel):
    Id: Optional[str] = None
    LineNum: Optional[int] = None
    Amount: float
    DetailType: str = "SalesItemLineDetail"
    Description: Optional[str] = None

    SalesItemLineDetail: Optional[Dict[str, Any]] = None

    @validator("Amount")
    def validate_amount(cls, v):
        if v < 0:
            raise ValueError("Amount must be positive")
        return v


class CustomerRef(BaseModel):
    value: str
    name: Optional[str] = None


class CurrencyRef(BaseModel):
    value: str
    name: Optional[str] = None


class Invoice(BaseModel):
    Id: Optional[str] = None
    SyncToken: str = "0"
    domain: str = "QBO"
    sparse: bool = False

    DocNumber: Optional[str] = None
    TxnDate: Optional[str] = None
    DueDate: Optional[str] = None
    CustomerRef: CustomerRef

    Line: List[Dict[str, Any]] = []

    TotalAmt: Optional[float] = None
    Balance: Optional[float] = None
    Deposit: float = 0.0

    CurrencyRef: Optional[Dict[str, str]] = None
    ExchangeRate: Optional[float] = None
    GlobalTaxCalculation: str = "TaxExcluded"

    SalesTermRef: Optional[Dict[str, str]] = None

    BillAddr: Optional[Dict[str, Any]] = None
    ShipAddr: Optional[Dict[str, Any]] = None

    EmailStatus: str = "NotSet"
    BillEmail: Optional[Dict[str, str]] = None

    PrintStatus: str = "NotSet"
    TxnStatus: Optional[str] = None

    CustomField: List[Dict[str, Any]] = []

    MetaData: Optional[Dict[str, Any]] = None

    @validator("Line")
    def validate_lines(cls, v):
        if not v:
            raise ValueError("Invoice must have at least one line item")
        return v

    @validator("TxnDate", "DueDate")
    def validate_dates(cls, v):
        if v and v != "":
            try:
                from datetime import datetime

                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v


class Payment(BaseModel):
    Id: Optional[str] = None
    SyncToken: str = "0"
    domain: str = "QBO"
    sparse: bool = False

    TxnDate: Optional[str] = None
    CustomerRef: CustomerRef
    TotalAmt: float
    UnappliedAmt: Optional[float] = None
    ProcessPayment: bool = False

    PaymentMethodRef: Optional[Dict[str, str]] = None
    DepositToAccountRef: Optional[Dict[str, str]] = None

    CurrencyRef: Optional[Dict[str, str]] = None
    ExchangeRate: Optional[float] = None

    Line: List[Dict[str, Any]] = []

    PaymentRefNum: Optional[str] = None

    PrivateNote: Optional[str] = None

    MetaData: Optional[Dict[str, Any]] = None

    @validator("TotalAmt")
    def validate_total_amount(cls, v):
        if v <= 0:
            raise ValueError("Payment amount must be positive")
        return v

    @validator("TxnDate")
    def validate_date(cls, v):
        if v and v != "":
            try:
                from datetime import datetime

                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")
        return v


class QuickBooksInvoiceManager:
    def __init__(self, auth: QuickBooksAuth):
        self.auth = auth
        self.base_url = auth.discovery_url
        # Transaction id of the most recent Intuit API call (success or
        # failure) - callers can read this right after _make_request returns
        # to attach it to their own sync-log entries.
        self.last_intuit_tid: Optional[str] = None

    def _get_headers(self) -> Dict[str, str]:
        return self.auth.get_auth_headers()

    def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v3/company/{self.auth.realm_id}/{endpoint}"
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            self.last_intuit_tid = _extract_intuit_tid(response)
            logger.debug(f"QuickBooks API call {method} {endpoint} succeeded (intuit_tid={self.last_intuit_tid})")
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            self.last_intuit_tid = _extract_intuit_tid(e.response)
            # Get detailed error response from QuickBooks
            error_details = ""
            try:
                error_response = e.response.json()
                error_details = f" - Response: {error_response}"
            except:
                error_details = f" - Text: {e.response.text}"

            error_msg = (
                f"QuickBooks API request failed: {e.response.status_code}{error_details} "
                f"- Request data: {data} - intuit_tid: {self.last_intuit_tid}"
            )
            logger.error(error_msg)
            raise AuthClientError(error_msg)
        except requests.RequestException as e:
            logger.error(f"QuickBooks API request failed: {str(e)}")
            raise AuthClientError(f"QuickBooks API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse QuickBooks API response: {str(e)}")
            raise AuthClientError(f"Invalid JSON response from QuickBooks API")

    def create_invoice(self, invoice: Invoice) -> Invoice:
        try:
            invoice_data = invoice.dict(exclude_none=True, exclude={"Id"})

            logger.info(f"Creating invoice for customer: {invoice.CustomerRef.value}")
            response = self._make_request("POST", "invoice", {"Invoice": invoice_data})

            if "QueryResponse" in response:
                created_invoice = response["QueryResponse"]["Invoice"][0]
            elif "Invoice" in response:
                created_invoice = response["Invoice"]
            else:
                raise AuthClientError("Unexpected response format from QuickBooks API")

            logger.info(
                f"Successfully created invoice with ID: {created_invoice.get('Id')}"
            )
            return Invoice(**created_invoice)

        except Exception as e:
            logger.error(f"Failed to create invoice: {str(e)}")
            raise AuthClientError(f"Failed to create invoice: {str(e)}")

    def update_invoice(self, invoice: Invoice) -> Invoice:
        """Update an existing invoice (requires Id + current SyncToken).

        Used for consolidated family invoicing, where a new line is appended
        (or an existing line's amount changed) as more children/charges are
        billed to the same guardian invoice, rather than creating a new
        invoice per charge.
        """
        if not invoice.Id:
            raise ValueError("update_invoice requires an invoice with an Id")
        try:
            invoice_data = invoice.dict(exclude_none=True)

            logger.info(f"Updating invoice ID: {invoice.Id}")
            response = self._make_request("POST", "invoice", {"Invoice": invoice_data})

            if "QueryResponse" in response:
                updated_invoice = response["QueryResponse"]["Invoice"][0]
            elif "Invoice" in response:
                updated_invoice = response["Invoice"]
            else:
                raise AuthClientError("Unexpected response format from QuickBooks API")

            logger.info(f"Successfully updated invoice with ID: {updated_invoice.get('Id')}")
            return Invoice(**updated_invoice)

        except Exception as e:
            logger.error(f"Failed to update invoice {invoice.Id}: {str(e)}")
            raise AuthClientError(f"Failed to update invoice: {str(e)}")

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        try:
            logger.info(f"Retrieving invoice ID: {invoice_id}")
            response = self._make_request("GET", f"invoice/{invoice_id}")

            if "QueryResponse" in response and response["QueryResponse"]:
                invoice_data = response["QueryResponse"]["Invoice"][0]
                return Invoice(**invoice_data)

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve invoice {invoice_id}: {str(e)}")
            raise AuthClientError(f"Failed to retrieve invoice: {str(e)}")

    def create_payment(self, payment: Payment) -> Payment:
        try:
            payment_data = payment.dict(exclude_none=True, exclude={"Id"})

            logger.info(f"Creating payment for customer: {payment.CustomerRef.value}")
            response = self._make_request("POST", "payment", {"Payment": payment_data})

            if "QueryResponse" in response:
                created_payment = response["QueryResponse"]["Payment"][0]
            elif "Payment" in response:
                created_payment = response["Payment"]
            else:
                raise AuthClientError("Unexpected response format from QuickBooks API")

            logger.info(
                f"Successfully created payment with ID: {created_payment.get('Id')}"
            )
            return Payment(**created_payment)

        except Exception as e:
            logger.error(f"Failed to create payment: {str(e)}")
            raise AuthClientError(f"Failed to create payment: {str(e)}")

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        try:
            logger.info(f"Retrieving payment ID: {payment_id}")
            response = self._make_request("GET", f"payment/{payment_id}")

            if "QueryResponse" in response and response["QueryResponse"]:
                payment_data = response["QueryResponse"]["Payment"][0]
                return Payment(**payment_data)

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve payment {payment_id}: {str(e)}")
            raise AuthClientError(f"Failed to retrieve payment: {str(e)}")

    def update_payment(self, payment: Payment) -> Payment:
        """Update an existing payment (requires Id + current SyncToken).

        Used to attach a ``LinkedTxn`` to a payment that was first created
        without an invoice (unapplied credit) once the invoice exists.
        """
        if not payment.Id:
            raise ValueError("update_payment requires a payment with an Id")
        try:
            payment_data = payment.dict(exclude_none=True)
            logger.info(f"Updating payment ID: {payment.Id}")
            response = self._make_request("POST", "payment", {"Payment": payment_data})

            if "QueryResponse" in response:
                updated = response["QueryResponse"]["Payment"][0]
            elif "Payment" in response:
                updated = response["Payment"]
            else:
                raise AuthClientError("Unexpected response format from QuickBooks API")
            return Payment(**updated)

        except Exception as e:
            logger.error(f"Failed to update payment {payment.Id}: {str(e)}")
            raise AuthClientError(f"Failed to update payment: {str(e)}")

    def _query_transactions(
        self, entity: str, model, since: Optional[str], page_size: int
    ) -> List[Any]:
        """Page through every ``entity`` row via STARTPOSITION/MAXRESULTS.

        ``since`` is an ISO-8601 timestamp; when given, only rows whose
        ``MetaData.LastUpdatedTime`` is at or after it are returned. A single
        unparseable row is skipped with a warning rather than aborting the run.
        """
        from urllib.parse import quote_plus

        page_size = max(1, min(page_size, 1000))
        where = ""
        if since:
            safe_since = str(since).replace("'", "")
            where = f" WHERE MetaData.LastUpdatedTime >= '{safe_since}'"

        results: List[Any] = []
        start = 1
        while True:
            query = (
                f"SELECT * FROM {entity}{where} "
                f"STARTPOSITION {start} MAXRESULTS {page_size}"
            )
            response = self._make_request("GET", f"query?query={quote_plus(query)}")

            rows = []
            if "QueryResponse" in response and entity in response["QueryResponse"]:
                rows = response["QueryResponse"][entity]

            for row in rows:
                try:
                    results.append(model(**row))
                except Exception as e:
                    logger.warning(
                        f"Skipping unparseable {entity} {row.get('Id')}: {e}"
                    )

            if len(rows) < page_size:
                break
            start += page_size

        logger.info(f"Retrieved {len(results)} {entity} records from QuickBooks")
        return results

    def list_invoices(
        self, since: Optional[str] = None, page_size: int = 1000
    ) -> List[Invoice]:
        """List invoices from QuickBooks, paging through the full result set.

        ``since`` (e.g. ``"2024-01-01"`` or ``"2024-01-01T00:00:00-07:00"``)
        limits the result to invoices changed at or after that time. Used by
        the reconciliation/linking pass to find invoices the school already has
        in QuickBooks so Pinewood links to them instead of creating duplicates.
        """
        return self._query_transactions("Invoice", Invoice, since, page_size)

    def list_payments(
        self, since: Optional[str] = None, page_size: int = 1000
    ) -> List[Payment]:
        """List payments from QuickBooks. See :meth:`list_invoices` for ``since``."""
        return self._query_transactions("Payment", Payment, since, page_size)

    def get_items(self) -> List[Dict[str, Any]]:
        try:
            logger.info("Retrieving items from QuickBooks")
            response = self._make_request(
                "GET",
                "query?query=SELECT * FROM Item WHERE Type='Service' OR Type='NonInventory' MAXRESULTS 100",
            )

            items = []
            if "QueryResponse" in response and "Item" in response["QueryResponse"]:
                items = response["QueryResponse"]["Item"]

            logger.info(f"Retrieved {len(items)} items")
            return items

        except Exception as e:
            logger.error(f"Failed to retrieve items: {str(e)}")
            raise AuthClientError(f"Failed to retrieve items: {str(e)}")

    def get_payment_methods(self) -> List[Dict[str, Any]]:
        try:
            logger.info("Retrieving payment methods from QuickBooks")
            response = self._make_request(
                "GET", "query?query=SELECT * FROM PaymentMethod MAXRESULTS 50"
            )

            methods = []
            if (
                "QueryResponse" in response
                and "PaymentMethod" in response["QueryResponse"]
            ):
                methods = response["QueryResponse"]["PaymentMethod"]

            logger.info(f"Retrieved {len(methods)} payment methods")
            return methods

        except Exception as e:
            logger.error(f"Failed to retrieve payment methods: {str(e)}")
            raise AuthClientError(f"Failed to retrieve payment methods: {str(e)}")


def create_fee_invoice(
    customer_id: str,
    customer_name: str,
    fee_items: List[Dict[str, Any]],
    currency_code: str = "ZMW",
    due_date: str = None,
    item_ref: Optional[Dict[str, str]] = None,
) -> Invoice:
    """Build (not send) an Invoice for a set of fee line items.

    ``item_ref`` is the QuickBooks ``ItemRef`` every line is booked against
    (``{"value": <Item.Id>, "name": <label>}``). It defaults to id ``"1"`` only
    as a last resort - callers should pass the tenant's configured service item
    so charges land in the right income account.
    """
    from datetime import datetime

    item_ref = item_ref or {"value": "1", "name": "Services"}

    lines = []
    total_amount = 0

    for i, fee_item in enumerate(fee_items, 1):
        amount = float(fee_item["amount"])
        total_amount += amount

        # Invoice.Line is typed List[Dict]; hand it plain dicts, not Line models.
        lines.append(Line(
            LineNum=i,
            Amount=amount,
            Description=fee_item.get("description", fee_item["name"]),
            DetailType="SalesItemLineDetail",
            SalesItemLineDetail={
                "ItemRef": item_ref,
                "UnitPrice": amount,
                "Qty": 1,
            },
        ).dict(exclude_none=True))

    customer_ref = CustomerRef(value=customer_id, name=customer_name)

    currency_ref = None
    if currency_code and currency_code != "USD":
        currency_ref = {"value": currency_code, "name": currency_code}

    invoice = Invoice(
        CustomerRef=customer_ref,
        Line=lines,
        TxnDate=datetime.now().strftime("%Y-%m-%d"),
        DueDate=due_date or datetime.now().strftime("%Y-%m-%d"),
        CurrencyRef=currency_ref,
        TotalAmt=total_amount,
    )

    return invoice


def create_fee_payment(
    customer_id: str,
    customer_name: str,
    amount: float,
    invoice_id: str = None,
    payment_method: str = None,
    reference_number: str = None,
    currency_code: str = "ZMW",
) -> Payment:
    from datetime import datetime

    customer_ref = CustomerRef(value=customer_id, name=customer_name)

    currency_ref = None
    if currency_code and currency_code != "USD":
        currency_ref = {"value": currency_code, "name": currency_code}

    lines = []
    if invoice_id:
        lines.append(
            {
                "Amount": amount,
                "LinkedTxn": [{"TxnId": invoice_id, "TxnType": "Invoice"}],
            }
        )

    payment_method_ref = None
    if payment_method:
        payment_method_ref = {"value": payment_method}

    payment = Payment(
        CustomerRef=customer_ref,
        TotalAmt=amount,
        TxnDate=datetime.now().strftime("%Y-%m-%d"),
        Line=lines,
        PaymentMethodRef=payment_method_ref,
        PaymentRefNum=reference_number,
        CurrencyRef=currency_ref,
    )

    return payment
