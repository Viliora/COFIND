"""Unit test untuk validasi/transform murni di review_utils (tanpa DB)."""

import base64
import review_utils as ru


def test_review_image_data_byte_len_empty():
    assert ru._review_image_data_byte_len(None) == 0
    assert ru._review_image_data_byte_len('') == 0


def test_review_image_data_byte_len_raw_string():
    s = 'hello'
    assert ru._review_image_data_byte_len(s) == len(s.encode('utf-8'))


def test_review_image_data_byte_len_data_url():
    raw = b'\xff\xd8\xff'
    b64 = base64.b64encode(raw).decode('ascii')
    data_url = f'data:image/jpeg;base64,{b64}'
    assert ru._review_image_data_byte_len(data_url) == len(raw)


def test_review_image_data_byte_len_invalid_base64():
    # validate=False dapat menghasilkan decode kosong / panjang 0, bukan selalu None
    n = ru._review_image_data_byte_len('data:image/png;base64,!!!')
    assert n is None or n == 0


def test_validate_review_photos_size_ok():
    tiny = base64.b64encode(b'x').decode('ascii')
    photos = [{'image_data': f'data:image/jpeg;base64,{tiny}'}]
    assert ru._validate_review_photos_size(photos) is None


def test_validate_review_photos_size_too_large():
    big = b'x' * (ru.MAX_REVIEW_PHOTO_BYTES + 1)
    b64 = base64.b64encode(big).decode('ascii')
    photos = [{'image_data': f'data:image/jpeg;base64,{b64}'}]
    err = ru._validate_review_photos_size(photos)
    assert err is not None
    assert '2 MB' in err or 'MB' in err


def test_validate_rating():
    assert ru._validate_rating(1) is True
    assert ru._validate_rating(5) is True
    assert ru._validate_rating(0) is False
    assert ru._validate_rating(6) is False
    assert ru._validate_rating(None, allow_none=True) is True
    assert ru._validate_rating(None, allow_none=False) is False
