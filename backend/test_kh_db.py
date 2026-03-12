"""
Kitchen Herald Database — Connection & Query Verification Script
Runs against the kitchen_herald MySQL database to validate:
  1. Connection works
  2. All tables exist with expected row counts
  3. Sample queries execute correctly (articles, events, jobs)
  4. KH Repository extraction works end-to-end

Usage:  python test_kh_db.py   (from backend/ directory)
"""
import sys
import os

# Ensure we can import app modules
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    db_uri = os.getenv("KH_DB_URI")
    if not db_uri:
        print("❌ KH_DB_URI not found in .env")
        sys.exit(1)
    print(f"📡 Connecting to: {db_uri.split('@')[1] if '@' in db_uri else db_uri}")
    return create_engine(db_uri, pool_pre_ping=True)


def test_connection(engine):
    """Test basic MySQL connection."""
    print("\n" + "=" * 60)
    print("TEST 1: Database Connection")
    print("=" * 60)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            print(f"  ✅ Connection successful (SELECT 1 = {result})")
            
            # Get database name
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
            print(f"  📦 Database: {db_name}")
            return True
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False


def test_tables(engine):
    """Verify all expected tables exist with row counts."""
    print("\n" + "=" * 60)
    print("TEST 2: Table Verification")
    print("=" * 60)
    
    expected_tables = [
        "users", "authors", "categories", "subcategories",
        "tags", "articles", "article_tags", "comments",
        "events", "job_vacancies", "advertisers", "newsletter_subscribers",
    ]
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    all_found = True
    for table in expected_tables:
        if table in existing_tables:
            with engine.connect() as conn:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  ✅ {table:30s} → {count} rows")
        else:
            print(f"  ❌ {table:30s} → MISSING!")
            all_found = False
    
    return all_found


def test_sample_queries(engine):
    """Run the sample queries from the schema."""
    print("\n" + "=" * 60)
    print("TEST 3: Sample Queries")
    print("=" * 60)
    
    queries = {
        "Q1: Latest published articles": """
            SELECT a.article_id, a.title, a.published_at, au.display_name AS author,
                   c.name AS category, sc.name AS subcategory
            FROM   articles a
            JOIN   authors      au ON a.author_id      = au.author_id
            JOIN   categories   c  ON a.category_id    = c.category_id
            LEFT JOIN subcategories sc ON a.subcategory_id = sc.subcategory_id
            WHERE  a.status = 'published'
            ORDER  BY a.published_at DESC
            LIMIT  5
        """,
        "Q2: Articles with tags": """
            SELECT a.title, GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR ', ') AS tags
            FROM   articles a
            JOIN   article_tags at2 ON a.article_id = at2.article_id
            JOIN   tags t           ON at2.tag_id    = t.tag_id
            GROUP  BY a.article_id
            LIMIT  5
        """,
        "Q3: Featured slider articles": """
            SELECT title, slug, published_at FROM articles
            WHERE  is_featured = TRUE AND status = 'published'
            ORDER  BY published_at DESC
        """,
        "Q4: Active job vacancies": """
            SELECT title, company_name, location, job_type, expires_at
            FROM   job_vacancies
            WHERE  is_active = TRUE AND (expires_at IS NULL OR expires_at >= CURDATE())
            ORDER  BY posted_at DESC
        """,
        "Q5: Upcoming events": """
            SELECT title, venue, city, event_date_start, organizer
            FROM   events
            WHERE  status = 'upcoming' AND event_date_start >= CURDATE()
            ORDER  BY event_date_start ASC
        """,
        "Q6: Confirmed subscribers": """
            SELECT COUNT(*) AS confirmed_subscribers FROM newsletter_subscribers
            WHERE  is_confirmed = TRUE AND unsubscribed_at IS NULL
        """,
    }
    
    all_passed = True
    for name, sql in queries.items():
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(sql)).fetchall()
                print(f"\n  📊 {name}  →  {len(rows)} result(s)")
                for row in rows[:3]:
                    # Print first 3 rows, truncating long values
                    row_dict = row._mapping
                    display = {k: (str(v)[:60] + "..." if len(str(v)) > 60 else v) 
                              for k, v in row_dict.items()}
                    print(f"     {display}")
                if len(rows) > 3:
                    print(f"     ... and {len(rows) - 3} more")
        except Exception as e:
            print(f"\n  ❌ {name}  →  FAILED: {e}")
            all_passed = False
    
    return all_passed


def test_kh_repository():
    """Test the KitchenHeraldRepository extraction."""
    print("\n" + "=" * 60)
    print("TEST 4: KH Repository Extraction")
    print("=" * 60)
    
    try:
        from app.repositories.kh_repository import KitchenHeraldRepository
        repo = KitchenHeraldRepository()
        
        # Test individual counts
        article_count = repo.get_article_count()
        event_count = repo.get_event_count()
        job_count = repo.get_job_count()
        
        print(f"  📰 Published articles: {article_count}")
        print(f"  📅 Upcoming events:    {event_count}")
        print(f"  💼 Active jobs:        {job_count}")
        
        # Test full extraction
        documents = repo.extract_all_content()
        print(f"\n  📦 Total documents extracted: {len(documents)}")
        
        # Show document breakdown by type
        by_type = {}
        for doc in documents:
            by_type[doc.doc_type] = by_type.get(doc.doc_type, 0) + 1
        for dtype, count in sorted(by_type.items()):
            print(f"     {dtype}: {count}")
        
        # Show first 3 document titles + content preview
        print(f"\n  📝 Sample extracted documents:")
        for doc in documents[:5]:
            print(f"     [{doc.doc_type}] {doc.title[:70]}")
            print(f"        Content preview: {doc.content[:100]}...")
            print(f"        Metadata keys: {list(doc.metadata.keys())}")
            print()
        
        return len(documents) > 0
    except Exception as e:
        print(f"  ❌ Repository test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("🍳 Kitchen Herald Database Verification")
    print("=" * 60)
    
    engine = get_engine()
    
    results = []
    results.append(("Connection", test_connection(engine)))
    results.append(("Tables", test_tables(engine)))
    results.append(("Queries", test_sample_queries(engine)))
    results.append(("Repository", test_kh_repository()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_pass = False
    
    print()
    if all_pass:
        print("🎉 All tests passed! Database is correctly configured.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
