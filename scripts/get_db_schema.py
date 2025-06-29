import sqlite3
import argparse
import os

def generate_schema_description(db_path: str) -> str:
    """
    Connects to a SQLite database and generates a text description of its schema.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        str: A formatted string describing the database schema.
    """
    if not os.path.exists(db_path):
        return f"Error: Database file not found at '{db_path}'"

    output_lines = []
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # --- Get a list of all tables ---
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]

            output_lines.append(f"╔════════════════════════════════════════════╗")
            output_lines.append(f"║   Database Schema: {os.path.basename(db_path):<25} ║")
            output_lines.append(f"╚════════════════════════════════════════════╝")
            output_lines.append(f"\nFound {len(tables)} table(s).\n")

            if not tables:
                return "\n".join(output_lines)

            # --- Process each table ---
            for table_name in tables:
                output_lines.append(f"\n────────────────── TABLE: {table_name} ──────────────────")

                # --- Get column information ---
                output_lines.append("  Columns:")
                cursor.execute(f'PRAGMA table_info("{table_name}");')
                columns = cursor.fetchall()
                # Column info structure: (cid, name, type, notnull, dflt_value, pk)
                for col in columns:
                    col_id, name, data_type, notnull, default_val, is_pk = col
                    constraints = []
                    if is_pk:
                        constraints.append("PRIMARY KEY")
                    if notnull and not is_pk: # PK is implicitly NOT NULL
                        constraints.append("NOT NULL")
                    if default_val is not None:
                        constraints.append(f"DEFAULT {default_val}")
                    
                    constraint_str = f"  [{', '.join(constraints)}]" if constraints else ""
                    output_lines.append(f"    - {name:<20} ({data_type.upper()}){constraint_str}")
                
                # --- Get foreign key information ---
                cursor.execute(f'PRAGMA foreign_key_list("{table_name}");')
                foreign_keys = cursor.fetchall()
                # FK info structure: (id, seq, table, from, to, on_update, on_delete, match)
                if foreign_keys:
                    output_lines.append("\n  Relationships (Foreign Keys):")
                    for fk in foreign_keys:
                        fk_id, seq, other_table, from_col, to_col, on_update, on_delete, match = fk
                        output_lines.append(
                            f"    - {from_col}  ───>  {other_table}({to_col}) "
                            f"[ON UPDATE {on_update}, ON DELETE {on_delete}]"
                        )
                
                # --- Get index information ---
                cursor.execute(f'PRAGMA index_list("{table_name}");')
                indexes = [row for row in cursor.fetchall() if not row[1].startswith('sqlite_autoindex')]
                # Index list structure: (seq, name, unique, origin, partial)
                if indexes:
                    output_lines.append("\n  Indexes:")
                    for idx in indexes:
                        idx_seq, idx_name, is_unique, origin, is_partial = idx
                        unique_str = "UNIQUE" if is_unique else ""
                        
                        # Get columns for this index
                        cursor.execute(f'PRAGMA index_info("{idx_name}");')
                        index_cols = [row[2] for row in cursor.fetchall()]
                        cols_str = ", ".join(index_cols)

                        output_lines.append(f"    - {idx_name:<25} ({unique_str} INDEX on {cols_str})")

        return "\n".join(output_lines)
    
    except sqlite3.Error as e:
        return f"An error occurred while accessing the database: {e}"

def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a human-readable schema description from a SQLite database file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "db_file",
        type=str,
        help="Path to the SQLite database file."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Optional. Path to save the schema description text file."
    )

    args = parser.parse_args()

    schema_text = generate_schema_description(args.db_file)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(schema_text)
            print(f"Schema successfully exported to '{args.output}'")
        except IOError as e:
            print(f"Error writing to file: {e}")
    else:
        print(schema_text)

if __name__ == "__main__":
    main()