"""Create a TOTP secret, show it as a QR code and print JARVIS_TOTP_SECRET.

Usage: python -m app.totp_setup
"""

import pyotp
import qrcode

from app.auth.totp import provisioning_uri, verify_code


def main() -> None:
    secret = pyotp.random_base32()
    qr = qrcode.QRCode(border=2)
    qr.add_data(provisioning_uri(secret, "dashboard"))
    print("Scan this QR code with your authenticator app (Aegis, Google Authenticator...):\n")
    qr.print_ascii(invert=True)
    print(f"\nOr enter this key by hand: {secret}")
    print("Keep it secret: anyone with this key can generate your codes.\n")

    for _ in range(3):
        if verify_code(secret, input("Code shown by the app: ").strip(), None) is not None:
            print("\nAdd this line to .env, then restart the backend:")
            print(f"JARVIS_TOTP_SECRET={secret}")
            return
        print("Wrong code, check the phone's clock and try again.")
    raise SystemExit("Setup cancelled: no valid code. Run the command again.")


if __name__ == "__main__":
    main()
