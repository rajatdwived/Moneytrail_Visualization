import csv, random
from datetime import datetime, timedelta

# -------------------- CONFIG --------------------
TXN_COUNTS = {
    "SBI": 180,      # SBI ke 180 transactions
    "HDFC": 250,     # HDFC ke 250 transactions
    "ICICI": 320     # ICICI ke 320 transactions
}
START_DATE = datetime(2025, 9, 1, 8, 0, 0)
CHANNELS = ["NEFT", "IMPS", "RTGS", "UPI"]
NAMES = [
    "Aman Sharma","Neha Verma","Rohit Gupta","Priya Singh","Vikram Patel",
    "Sanjay Rao","Anjali Mehta","Karan Jain","Isha Kapoor","Rahul Chandra",
    "Sunita Nair","Deepak Kulkarni","Pooja Reddy","Rakesh Menon","Manisha Iyer",
    "Aarti Bhat","Mohit Khanna","Shreya Bose","Aditya Desai","Sneha Joshi",
    "Kajal Thomas","Vikas Yadav","Nitin Kumar","Meera Mohan","Parth Shah",
    "Rina Dutta","Arjun Nair","Geeta Reddy","Sahil Sinha","Neeraj Roy",
    "Tanvi Agarwal","Pranav Mitra","Komal Ghosh","Naveen Pillai","Ritu Kapoor",
    "Yash Chauhan","Mitali Banerjee","Harshal Dixit","Sonia Deshmukh","Ankit Saxena"
]
BANK_PREFIX = {"SBI": "10", "HDFC": "20", "ICICI": "30"}
# -------------------------------------------------

def account_number(bank):
    prefix = BANK_PREFIX[bank]
    suffix = "".join(str(random.randint(0,9)) for _ in range(14))  # 16 digits total
    return prefix + suffix

def generate_bank_data(bank, count):
    current_time = START_DATE
    rows = []
    for i in range(1, count+1):
        current_time += timedelta(minutes=random.randint(1, 180))
        txn_id = f"{bank[:2]}{i:06d}"

        sender_acc = account_number(bank)
        receiver_acc = account_number(bank)
        while receiver_acc == sender_acc:
            receiver_acc = account_number(bank)

        sender_name = random.choice(NAMES)
        receiver_name = random.choice(NAMES)
        while receiver_name == sender_name:
            receiver_name = random.choice(NAMES)

        # amount distribution realistic
        r = random.random()
        if r < 0.7:
            amount = random.randint(500, 25000)
        elif r < 0.9:
            amount = random.randint(25001, 200000)
        else:
            amount = random.randint(200001, 1500000)

        channel = random.choices(CHANNELS, weights=[0.35,0.35,0.2,0.1])[0]

        rows.append({
            "bank": bank,
            "txn_id": txn_id,
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "sender_account": sender_acc,
            "sender_name": sender_name,
            "receiver_account": receiver_acc,
            "receiver_name": receiver_name,
            "amount": amount,
            "channel": channel
        })
    return rows

def write_csv(filename, rows):
    fields = ["bank","txn_id","timestamp","sender_account","sender_name",
              "receiver_account","receiver_name","amount","channel"]
    with open(filename,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

if __name__ == "__main__":
    random.seed(42)
    all_rows = []
    for bank, count in TXN_COUNTS.items():
        rows = generate_bank_data(bank, count)
        file = f"data_{bank.lower()}.csv"
        write_csv(file, rows)
        all_rows += rows
        print(f"✅ {bank}: {count} transactions → {file}")

    # also make a combined dataset
    write_csv("all_banks_combined.csv", all_rows)
    print("🎉 All bank datasets generated successfully!")
