#!/usr/bin/env python3
"""
Fedena to Pinewood Data Migration Script

This script migrates data from the fedena_pinewood.sql file (MySQL/MariaDB dump)
to the PostgreSQL database running in the Docker container.

Usage:
    python migrate_fedena_data.py [--dry-run] [--table TABLE_NAME]
"""

import os
import re
import sys
import psycopg2
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class FedenaDataMigrator:
    """Handles migration of Fedena data from MySQL dump to PostgreSQL."""

    def __init__(self, sql_file: str, db_config: Dict[str, str], dry_run: bool = False):
        self.sql_file = Path(sql_file)
        self.db_config = db_config
        self.dry_run = dry_run
        self.connection = None

        # Track migration statistics
        self.stats = {
            'tables_processed': 0,
            'records_inserted': 0,
            'errors': []
        }

    def connect_to_database(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )
            self.connection.autocommit = True
            print(f"✓ Connected to PostgreSQL database: {self.db_config['database']}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to database: {e}")
            return False

    def parse_mysql_dump(self) -> List[Dict]:
        """Parse the MySQL dump file and extract table definitions and data."""
        if not self.sql_file.exists():
            raise FileNotFoundError(f"SQL file not found: {self.sql_file}")

        print(f"📖 Reading SQL file: {self.sql_file}")

        with open(self.sql_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove MySQL-specific comments and commands
        content = self._clean_mysql_syntax(content)

        # Extract table creation statements and insert statements
        tables = self._extract_tables(content)

        print(f"📊 Found {len(tables)} tables in SQL dump")
        return tables

    def _clean_mysql_syntax(self, content: str) -> str:
        """Remove MySQL-specific syntax that doesn't work in PostgreSQL."""
        # Remove MySQL-specific comments
        content = re.sub(r'/\*![0-9]*.*?\*/', '', content, flags=re.DOTALL)

        # Remove LOCK/UNLOCK TABLES statements
        content = re.sub(r'LOCK TABLES.*?;', '', content, flags=re.IGNORECASE)
        content = re.sub(r'UNLOCK TABLES;', '', content, flags=re.IGNORECASE)

        # Remove MySQL-specific SET statements
        content = re.sub(r'SET @.*?;', '', content, flags=re.IGNORECASE)
        content = re.sub(r'SET @@.*?;', '', content, flags=re.IGNORECASE)

        return content

    def _extract_tables(self, content: str) -> List[Dict]:
        """Extract table definitions and data from SQL content."""
        tables = []

        # Pattern to match CREATE TABLE statements
        create_pattern = r'CREATE TABLE `([^`]+)`\s*\((.*?)\)\s*ENGINE[^;]*;'

        # Pattern to match INSERT statements
        insert_pattern = r'INSERT INTO `([^`]+)`[^(]*\((.*?)\)\s*VALUES\s*(.*?);'

        # Find all CREATE TABLE statements
        create_matches = re.finditer(create_pattern, content, re.DOTALL | re.IGNORECASE)

        for create_match in create_matches:
            table_name = create_match.group(1)
            table_definition = create_match.group(2)

            # Convert MySQL table definition to PostgreSQL
            pg_definition = self._convert_table_definition(table_definition)

            # Find corresponding INSERT statements
            insert_matches = re.finditer(
                insert_pattern.replace('([^`]+)', re.escape(table_name)),
                content,
                re.DOTALL | re.IGNORECASE
            )

            insert_data = []
            for insert_match in insert_matches:
                columns = [col.strip('`').strip() for col in insert_match.group(2).split(',')]
                values_text = insert_match.group(3)

                # Parse VALUES data
                values_list = self._parse_values(values_text)
                insert_data.extend([(columns, values) for values in values_list])

            tables.append({
                'name': table_name,
                'definition': pg_definition,
                'columns': self._extract_columns_from_definition(table_definition),
                'data': insert_data
            })

        return tables

    def _convert_table_definition(self, mysql_def: str) -> str:
        """Convert MySQL table definition to PostgreSQL syntax."""
        # Convert common MySQL types to PostgreSQL types
        type_mappings = {
            r'int\(11\)': 'INTEGER',
            r'tinyint\(1\)': 'BOOLEAN',
            r'varchar\((\d+)\)': r'VARCHAR(\1)',
            r'text': 'TEXT',
            r'datetime': 'TIMESTAMP',
            r'date': 'DATE',
            r'decimal\((\d+),(\d+)\)': r'DECIMAL(\1,\2)',
            r'float': 'REAL',
            r'double': 'DOUBLE PRECISION'
        }

        pg_def = mysql_def
        for mysql_type, pg_type in type_mappings.items():
            pg_def = re.sub(mysql_type, pg_type, pg_def, flags=re.IGNORECASE)

        # Convert AUTO_INCREMENT to SERIAL
        pg_def = re.sub(r'AUTO_INCREMENT', 'SERIAL', pg_def, flags=re.IGNORECASE)

        # Remove MySQL-specific options
        pg_def = re.sub(r'ENGINE=\w+', '', pg_def, flags=re.IGNORECASE)
        pg_def = re.sub(r'DEFAULT CHARSET=\w+', '', pg_def, flags=re.IGNORECASE)
        pg_def = re.sub(r'COLLATE=[\w_]+', '', pg_def, flags=re.IGNORECASE)

        # Remove backticks
        pg_def = pg_def.replace('`', '"')

        return pg_def.strip()

    def _extract_columns_from_definition(self, table_def: str) -> List[str]:
        """Extract column names from table definition."""
        columns = []
        lines = table_def.split(',')

        for line in lines:
            line = line.strip()
            if line and not line.upper().startswith(('PRIMARY KEY', 'KEY', 'INDEX', 'UNIQUE')):
                # Extract column name (first word after backtick)
                match = re.match(r'`([^`]+)`', line)
                if match:
                    columns.append(match.group(1))

        return columns

    def _parse_values(self, values_text: str) -> List[List]:
        """Parse VALUES clause from INSERT statement."""
        values_list = []

        # Split by ),( to separate multiple value sets
        value_sets = re.findall(r'\((.*?)\)(?=,\s*\(|$)', values_text, re.DOTALL)

        for value_set in value_sets:
            values = []
            current_value = ""
            in_quotes = False
            quote_char = None

            i = 0
            while i < len(value_set):
                char = value_set[i]

                if char in ("'", '"') and not in_quotes:
                    in_quotes = True
                    quote_char = char
                    current_value += char
                elif char == quote_char and in_quotes:
                    # Check if it's escaped
                    if i + 1 < len(value_set) and value_set[i + 1] == quote_char:
                        current_value += char + char
                        i += 1
                    else:
                        in_quotes = False
                        quote_char = None
                        current_value += char
                elif char == ',' and not in_quotes:
                    values.append(self._clean_value(current_value.strip()))
                    current_value = ""
                else:
                    current_value += char

                i += 1

            # Add the last value
            if current_value.strip():
                values.append(self._clean_value(current_value.strip()))

            values_list.append(values)

        return values_list

    def _clean_value(self, value: str) -> Optional[str]:
        """Clean and convert MySQL values to PostgreSQL format."""
        value = value.strip()

        if value.upper() == 'NULL':
            return None

        # Handle quoted strings
        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            # Remove quotes and handle escaped quotes
            unquoted = value[1:-1]
            unquoted = unquoted.replace("\\'", "'").replace('\\"', '"')
            return unquoted

        # Handle boolean values
        if value in ('0', 'false', 'FALSE'):
            return 'false'
        elif value in ('1', 'true', 'TRUE'):
            return 'true'

        return value

    def migrate_table(self, table: Dict, target_table: Optional[str] = None) -> bool:
        """Migrate a single table to PostgreSQL."""
        table_name = target_table or table['name']

        print(f"\n🔄 Migrating table: {table['name']} -> {table_name}")

        if self.dry_run:
            print(f"   [DRY RUN] Would create table with {len(table['data'])} records")
            return True

        try:
            cursor = self.connection.cursor()

            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                );
            """, (table_name,))

            table_exists = cursor.fetchone()[0]

            if not table_exists:
                print(f"   ⚠️  Table {table_name} doesn't exist. You may need to run migrations first.")
                return False

            # Insert data
            if table['data']:
                insert_count = 0
                for columns, values in table['data']:
                    try:
                        # Prepare INSERT statement
                        placeholders = ', '.join(['%s'] * len(values))
                        column_names = ', '.join([f'"{col}"' for col in columns])

                        insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'

                        cursor.execute(insert_sql, values)
                        insert_count += 1

                    except Exception as e:
                        self.stats['errors'].append(f"Error inserting into {table_name}: {e}")
                        print(f"   ⚠️  Insert error: {e}")
                        continue

                print(f"   ✓ Inserted {insert_count} records")
                self.stats['records_inserted'] += insert_count
            else:
                print(f"   ℹ️  No data to insert")

            cursor.close()
            self.stats['tables_processed'] += 1
            return True

        except Exception as e:
            self.stats['errors'].append(f"Error migrating table {table_name}: {e}")
            print(f"   ✗ Migration failed: {e}")
            return False

    def migrate_all(self, target_table: Optional[str] = None) -> bool:
        """Migrate all tables from the SQL dump."""
        if not self.connect_to_database():
            return False

        try:
            tables = self.parse_mysql_dump()

            if target_table:
                # Migrate specific table only
                target_tables = [t for t in tables if t['name'] == target_table]
                if not target_tables:
                    print(f"✗ Table '{target_table}' not found in SQL dump")
                    return False
                tables = target_tables

            print(f"\n🚀 Starting migration of {len(tables)} table(s)...")

            success_count = 0
            for table in tables:
                if self.migrate_table(table):
                    success_count += 1

            # Print summary
            print(f"\n📊 Migration Summary:")
            print(f"   Tables processed: {self.stats['tables_processed']}")
            print(f"   Records inserted: {self.stats['records_inserted']}")
            print(f"   Successful tables: {success_count}/{len(tables)}")

            if self.stats['errors']:
                print(f"   Errors: {len(self.stats['errors'])}")
                for error in self.stats['errors'][:5]:  # Show first 5 errors
                    print(f"     - {error}")
                if len(self.stats['errors']) > 5:
                    print(f"     ... and {len(self.stats['errors']) - 5} more errors")

            return success_count == len(tables)

        except Exception as e:
            print(f"✗ Migration failed: {e}")
            return False

        finally:
            if self.connection:
                self.connection.close()
                print("🔐 Database connection closed")


def get_db_config_from_env() -> Dict[str, str]:
    """Get database configuration from environment variables."""
    return {
        'host': os.getenv('DATABASE_HOST', 'localhost'),
        'port': int(os.getenv('DATABASE_PORT', 5433)),  # Docker external port
        'database': os.getenv('DATABASE_NAME', 'pinewood_db'),
        'user': os.getenv('DATABASE_USER', 'pinewood'),
        'password': os.getenv('DATABASE_PASSWORD', '')
    }


def main():
    """Main entry point for the migration script."""
    print("=" * 70)
    print("⛔  DEPRECATED — DO NOT USE FOR PRODUCTION MIGRATIONS")
    print()
    print("  This script copies raw MySQL rows as-is. It does NOT perform:")
    print("  • UUID conversion (Pinewood requires UUID primary keys)")
    print("  • Tenant injection (required for multi-tenant schema isolation)")
    print("  • FK mapping (integer IDs → UUIDs)")
    print()
    print("  Use fedena_to_pinewood_transformer.py for all real migrations:")
    print("    python data_migration/fedena_to_pinewood_transformer.py \\")
    print("      --mysql --tenant-id <uuid> [--dry-run]")
    print("=" * 70)
    print()

    parser = argparse.ArgumentParser(description='Migrate Fedena data to Pinewood PostgreSQL database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without actually doing it')
    parser.add_argument('--table', help='Migrate only the specified table')
    parser.add_argument('--sql-file', default='fedena_pinewood.sql', help='Path to the SQL dump file')

    args = parser.parse_args()

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get database configuration
    db_config = get_db_config_from_env()

    # Determine SQL file path
    script_dir = Path(__file__).parent
    sql_file = script_dir / args.sql_file

    if not sql_file.exists():
        print(f"✗ SQL file not found: {sql_file}")
        sys.exit(1)

    print("🏗️  Fedena to Pinewood Data Migration")
    print("=" * 40)
    print(f"SQL File: {sql_file}")
    print(f"Database: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")

    if args.table:
        print(f"Target Table: {args.table}")

    print()

    # Create migrator and run migration
    migrator = FedenaDataMigrator(sql_file, db_config, dry_run=args.dry_run)

    try:
        success = migrator.migrate_all(target_table=args.table)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()