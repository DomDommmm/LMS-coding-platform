import httpx, hmac, hashlib
checksum_key = '4f526d4ad04a19e22dd22da8960c02d7570d09c12c3c8c97c47174fa8d4f77b5'
order_code = 1725624123456  # <-- Thay bằng orderCode của transaction bạn vừa tạo
data = {
    'orderCode': order_code,
    'amount': 299000,
    'description': f'LMS {order_code}',
    'accountNumber': '123456789',
    'reference': 'FT2609TEST',
    'transactionDateTime': '2026-09-06 16:20:00',
    'currency': 'VND',
    'paymentLinkId': 'paylink_test_123',
    'code': '00',
    'desc': 'success',
}
# Tạo signature chuẩn PayOS
query_str = '&'.join(f'{k}={data[k]}' for k in sorted(data.keys()))
signature = hmac.new(checksum_key.encode(), query_str.encode(), hashlib.sha256).hexdigest()
payload = {
    'code': '00',
    'desc': 'success',
    'data': data,
    'signature': signature
}
res = httpx.post('http://localhost:4000/api/payments/payos-webhook', json=payload)
print('Webhook Response:', res.status_code, res.json())