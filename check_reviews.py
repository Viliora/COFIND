import os
import sys
sys.path.append('.')

from app import app
from supabase import create_client

with app.app_context():
    try:
        supabase = create_client(
            os.getenv('SUPABASE_URL', 'https://your-project.supabase.co'),
            os.getenv('SUPABASE_ANON_KEY', 'your-anon-key')
        )

        # Check reviews for Aming Coffee
        result = supabase.table('reviews').select('id, place_id, user_id').eq('place_id', 'ChIJyRLXBlJYHS4RWNj0yvAvSAQ').execute()

        print('Reviews in Supabase for Aming Coffee (ChIJyRLXBlJYHS4RWNj0yvAvSAQ):')
        print(f'Count: {len(result.data) if result.data else 0}')

        if result.data:
            for review in result.data[:5]:
                print(f'- ID: {review["id"]}, User: {review["user_id"]}, Place: {review["place_id"]}')

        # Check all place_ids in reviews
        all_result = supabase.table('reviews').select('place_id').execute()
        if all_result.data:
            unique_place_ids = set(review['place_id'] for review in all_result.data)
            print(f'\nUnique place_ids in Supabase reviews: {len(unique_place_ids)}')
            for pid in list(unique_place_ids)[:10]:
                print(f'- {pid}')

    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()