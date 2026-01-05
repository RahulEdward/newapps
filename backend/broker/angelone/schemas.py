from pydantic import BaseModel

class AngelOneLoginRequest(BaseModel):
    api_key: str
    client_code: str
    password: str
    totp: str

class AngelOneOrderRequest(BaseModel):
    variety: str
    tradingsymbol: str
    symboltoken: str
    transactiontype: str
    exchange: str
    ordertype: str
    producttype: str
    duration: str
    price: str
    squareoff: str
    stoploss: str
    quantity: str
