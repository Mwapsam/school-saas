from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Generate key
key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)

# Private key (THIS goes to GitHub Secrets)
private_key = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
)

with open("cloudfront_private_key.pem", "wb") as f:
    f.write(private_key)

# Public key (THIS goes to AWS CloudFront)
public_key = key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

with open("cloudfront_public_key.pem", "wb") as f:
    f.write(public_key)

print("Keys generated successfully")