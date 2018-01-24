
'''
 SkateBot Auto trading Bot
 Desc: Market/trading routines
 (c) Joshith Rayaroth Koderi
'''
##############################################
###### Bugs/Caveats, TODOs, AIs###############
### 1. Account Remaining_size for fund calculations


##############################################

import json
import os
import uuid
import Queue
import pprint
from itertools import product
from docutils.nodes import sidebar
from decimal import Decimal

from utils import *
from order_book import OrderBook
from order import Order, TradeRequest
import db

log = getLogger ('MARKET')
log.setLevel(log.INFO)

SkateBot_market_list = []

# Feed Q routines
feedQ = Queue.Queue()
def feed_enQ (market, msg):
    obj = {"market":market, "msg":msg}
    feedQ.put(obj)
    
def feed_deQ (timeout):
    try:
        if (timeout == 0):
            msg = feedQ.get(False)
        else:
            msg = feedQ.get(block=True, timeout=timeout)
    except Queue.Empty:
        return None
    else:
        return msg

def feed_Q_process_msg (msg):
    log.debug ("-------feed msg -------")
    if (msg["market"]!= None):
        msg["market"].market_consume_feed(msg['msg'])

def get_market_list ():
    return SkateBot_market_list

def get_market_by_product (product_id):
    for market in SkateBot_market_list:
        if market.product_id == product_id:
            return market
        
def market_init (exchange_list):
    '''
    Initialize per exchange, per product data.
    This is where we want to keep all the run stats
    '''
    global SkateBot_market_list
    for exchange in exchange_list:
        for product in exchange.get_products():
            market = exchange.market_init (exchange, product)
            if (market == None):
                log.critical ("Market Init Failed for exchange: %s product: %s"%(exchange.__name__, product['id']))
            else:
                SkateBot_market_list.append(market)

class Fund:
    def __init__(self):
        self.initial_value = Decimal(0.0)
        self.current_value = Decimal(0.0)
        self.current_hold_value = Decimal(0.0)
        self.total_traded_value = Decimal(0.0)
        self.current_realized_profit = Decimal(0.0)
        self.current_unrealized_profit = Decimal(0.0)   
        self.total_profit = Decimal(0.0)
        self.current_avg_buy_price = Decimal(0.0)
        self.latest_buy_price = Decimal(0.0)         
        self.fund_liquidity_percent = Decimal(0.0)
        self.max_per_buy_fund_value = Decimal(0.0)
            
    def set_initial_value (self, value):
        self.initial_value = self.current_value = Decimal(value)
        
    def set_fund_liquidity_percent (self, value):
        self.fund_liquidity_percent = Decimal(value)
        
    def set_hold_value (self, value):
        self.current_hold_value = Decimal(value)      
        
    def set_max_per_buy_fund_value (self, value):
        self.max_per_buy_fund_value = Decimal(value)  

    def __str__(self):
        return ("{'initial_value':%g,'current_value':%g,'current_hold_value':%g,"
                "'total_traded_value':%g,'current_realized_profit':%g,'current_unrealized_profit':%g"
                ",'total_profit':%g,'current_avg_buy_price':%g,'latest_buy_price':%g,"
                "'fund_liquidity_percent':%g, 'max_per_buy_fund_value':%g}")%(
            self.initial_value, self.current_value, self.current_hold_value,
             self.total_traded_value,self.current_realized_profit, 
             self.current_unrealized_profit, self.total_profit, self.current_avg_buy_price, 
             self.latest_buy_price, self.fund_liquidity_percent, self.max_per_buy_fund_value )
                
class Crypto:
    def __init__(self):    
        self.initial_size = Decimal(0.0)
        self.current_size = Decimal(0.0)
        self.latest_traded_size = Decimal(0.0)
        self.current_hold_size = Decimal(0.0)
        self.total_traded_size = Decimal(0.0)
            
    def set_initial_size (self, size):
        self.initial_size = self.current_size = size
        
    def set_hold_size (self, size):
        self.current_hold_size = size

    def __str__(self):
        return ("{'initial_size':%g, 'current_size':%g, 'latest_traded_size':%g,"
                " 'current_hold_size':%g, 'total_traded_size':%g}")%(
            self.initial_size, self.current_size, self.latest_traded_size,
            self.current_hold_size, self.total_traded_size)
                
class Market:
#     '''
#     Initialize per exchange, per product data.
#     This is where we want to keep all the run stats
#     {
#      product_id :
#      product_name: 
#      exchange_name:
#      fund {
#      initial_value:   < Initial fund value >
#      current_value:
#      current_hold_value
#      total_traded_value:
#      current_realized_profit:
#      current_unrealized_profit
#      total_profit:
#      fund_liquidity_percent: <% of total initial fund allowed to use>     
#      max_per_buy_fund_value:
#      }
#      crypto {
#      initial_size:
#      current_size:
#      current_hold_size:
#      current_avg_value:
#      total_traded_size:
#      }
#      orders {
#      total_order_num
#      open_buy_orders_db: <dict>
#      open_sell_orders_db: <dict>
#      traded_buy_orders_db:
#      traded_sell_orders_db:
#      }
#     } 
#        trade_req
#         self.product = Product
#         self.side = Side
#         self.size = Size
#         self.type = Type
#         self.price = Price
#         
#     '''    
    def __init__(self, product=None, exchange=None):
        self.product_id = None if product == None else product['id']
        self.name = None if product == None else product['display_name']
        self.exchange_name = None if exchange == None else exchange.__name__
        self.exchange = exchange       #exchange module
        self.current_market_rate = Decimal(0.0)  
        self.consume_feed = None
        self.fund = Fund ()
        self.crypto = Crypto ()
        #self.order_book = Orders ()
        self.order_book = OrderBook(market=self)
        
    def set_market_price (self, price):
        self.current_market_rate = price
        
    def get_market_price (self):
        return self.current_market_rate       
        
    def market_consume_feed(self, msg):
        if (self.consume_feed != None):
            self.consume_feed(self, msg)
            
    def handle_pending_trades (self):
        #TODO: FIXME:jork: Might need to extend
        log.debug("(%d) Pending Trade Reqs "%(len(self.order_book.pending_trade_req)))

        if 0 == len(self.order_book.pending_trade_req):
            return 
        market_price = self.get_market_price()
        for trade_req in self.order_book.pending_trade_req[:]:
            if (trade_req.side == 'BUY'):
                if (trade_req.stop >= market_price):
                    self.buy_order_create(trade_req)
                    self.order_book.remove_pending_trade_req(trade_req)
                else:
                    log.debug("STOP BUY: market(%g) higher than STOP (%g)"%(self.current_market_rate, trade_req.stop))
            elif (trade_req.side <= 'SELL'):
                if (trade_req.stop <= market_price):
                    self.sell_order_create(trade_req)
                    self.order_book.remove_pending_trade_req(trade_req)     
                else:
                    log.debug("STOP SELL: market(%g) lower than STOP (%g)"%(self.current_market_rate, trade_req.stop))                                   
            
    def order_status_update (self, order):
        log.debug ("ORDER UPDATE: %s"%(str(order)))        
        
        side = order.side
        msg_type = order.status_type
        reason = order.status_reason
        if side == 'buy':
            if msg_type == 'done':
                #for an order done, get the order details
                order_det = self.exchange.get_order(order.id)
                if (order_det):
                    order = order_det
                if reason == 'filled':
                    self.buy_order_filled ( order)
                elif reason == 'canceled':
                    self.buy_order_canceled (order)
            elif msg_type == 'received':
                self.buy_order_received(order)
            else:
                log.debug ("Ignored/Unknown buy order status: %s"%(msg_type))
        elif side == 'sell':
            if msg_type == 'done':
                #for an order done, get the order details
                order_det = self.exchange.get_order(order.id)
                if (order_det):
                    order = order_det                
                if reason == 'filled':
                    self.sell_order_filled ( order)
                elif reason == 'canceled':
                    self.sell_order_canceled (order)
            elif msg_type == 'received':
                self.sell_order_received(order)
            else:
                log.debug ("Ignored/Unknown sell order status: %s"%(msg_type))     
        else:
            log.error ("Unknown order Side (%s)"%(side))
                    
    def buy_order_received (self, order):
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #successful order
            #update fund 
            order_type = market_order.order_type
            order_cost = 0
            if order_type == 'market':
                order_cost = Decimal(market_order.funds) 
            elif order_type == 'limit':
                order_cost = Decimal (market_order.price) * Decimal (market_order.size)
            else:
                log.error ("BUY: unknown order_type: %s"%(order_type))
                return
            self.fund.current_hold_value += order_cost
            self.fund.current_value -= order_cost
                                        
    def buy_order_create (self, trade_req):
        order = self.exchange.buy (trade_req)
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #successful order
            log.debug ("Order Sent to exchange. ")        
            
    def buy_order_filled (self, order):
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #Valid order          
            order_cost = (market_order.size*market_order.price)
            #fund
            self.fund.current_hold_value -= order_cost
            self.fund.latest_buy_price = market_order.price
            self.fund.total_traded_value += order_cost
            #avg cost
            curr_total_crypto_size = (self.crypto.current_hold_size + self.crypto.current_size)
            self.fund.current_avg_buy_price = (((self.fund.current_avg_buy_price *
                                                  curr_total_crypto_size) + (order_cost))/
                                                        (curr_total_crypto_size + market_order.size))
            #crypto
            self.crypto.current_size += market_order.size
            self.crypto.latest_traded_size = market_order.size
            self.crypto.total_traded_size += market_order.size
            
    def buy_order_canceled(self, order):
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #Valid order
            order_cost = (market_order.size*market_order.price)
            self.fund.current_hold_value -= order_cost
            self.fund.current_value += order_cost        
            
    def sell_order_create (self, trade_req):
        order = self.exchange.sell (trade_req)
        #update fund 
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #successful order
            pass

    def sell_order_received (self, order):
        #log.debug ("SELL RECV: %s"%(json.dumps(order, indent=4, sort_keys=True)))
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #successful order
            #update fund 
            order_type = market_order.order_type
            size = 0
            if order_type == 'market':
                size = Decimal(market_order.size) 
            elif order_type == 'limit':
                size = Decimal (market_order.size)
            else:
                log.error ("BUY: unknown order_type: %s"%(order_type))
                return
            self.crypto.current_hold_size += size
            self.crypto.current_size -= size            
                        
    def sell_order_filled (self, order):
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #Valid order       
            order_cost = (market_order.size*market_order.price)        
            #fund
            self.fund.current_value += order_cost
            #crypto
            self.crypto.current_hold_size -= market_order.size
            #profit
            profit = (market_order.price - self.fund.current_avg_buy_price )*market_order.size
            self.fund.current_realized_profit += profit
            
    def sell_order_canceled(self, order):
        market_order  =  self.order_book.add_or_update_my_order(order)
        if(market_order): #Valid order
            self.crypto.current_hold_size -= market_order.size
            self.crypto.current_size += market_order.size
            
    def set_current_market_rate(self, value):
        self.current_market_rate = Decimal(value)
        
    def __str__(self):
        return "{'product_id':%s,'name':%s,'exchange_name':%s,'fund':%s,'crypto':%s,'orders':%s}"%(
                self.product_id,self.name,self.exchange_name, 
                str(self.fund), str(self.crypto), str(self.order_book))
        
        
############# Market Class Def - end ############# 
def execute_market_trade(market, trade_req_list):
#    print ("Market: %s"%(str(market)))
    '''
    Desc: Execute a trade request on the market. 
          This API calls the sell/buy APIs of the corresponding exchanges 
          and expects the order in uniform format
    '''
    for trade_req in trade_req_list:
        log.debug ("Executing Trade Request:"+str(trade_req))
        if (trade_req.type == 'limit'):
            if (trade_req.side == 'BUY'):
                order = market.buy_order_create (trade_req)
            elif (trade_req.side == 'SELL'):
                order = market.sell_order_create (trade_req)
            if (order == None):
                log.error ("Placing Order Failed!")
                return
            #Add the successful order to the db
            save_order (market, trade_req, order)
        elif (trade_req.type == 'stop'):
            #  Stop order, add to pending list
            log.debug("pending(stop) trade_req %s"%(str(trade_req)))
            market.order_book.add_pending_trade_req(trade_req)
            
def save_order (market, trade_req, order):
    db.db_add_or_update_order (market, trade_req.product, order)
    #TODO: FIXME: jork: implement
    
    
def get_manual_trade_req (market):
    exchange_name = market.exchange.__name__
    trade_req_list = []
    manual_file_name = "override/TRADE_%s.%s"%(exchange_name, market.product_id)
    if os.path.isfile(manual_file_name):
        log.info ("Override file exists - "+manual_file_name)
        with open(manual_file_name) as fp:
            trade_req_dict = json.load(fp)
            #delete the file after reading to make sure multiple order from same orderfile
            os.remove(manual_file_name)
            # Validate
            if (trade_req_dict != None and trade_req_dict['product'] == market.product_id ):
                trade_req = TradeRequest(Product=trade_req_dict['product'],
                                          Side=trade_req_dict['side'],
                                           Size=trade_req_dict['size'],
                                            Type=trade_req_dict['type'],
                                             Price=trade_req_dict['price'],
                                             Stop=trade_req_dict['stop'])
                log.info("Valid manual order : %s"%(str(trade_req)))
                trade_req_list.append(trade_req)
    return trade_req_list       

def generate_trade_request (market, signal):
    '''
    Desc: Consider various parameters and generate a trade request
    Algo: 
    '''
    log.debug ('Calculate trade Req')
        #TODO: jork: implement
    return None


##########################################
############## Public APIs ###############    
def update_market_states (market):
    '''
    Desc: 1. Update/refresh the various market states (rate, etc.)
          2. perform any pending trades (stop requests)
          3. Cancel/timeout any open orders if need be
    '''
    #TODO: jork: implement    
    #1.update market states
    if (market.order_book.book_valid == False):
        log.debug ("Re-Construct the Order Book")
        market.order_book.reset_book()     
    #2.pending trades
    market.handle_pending_trades ()
    
def generate_trade_signal (market):
    """ 
    Do all the magic to generate the trade signal
    params : exchange, product
    return : trade signal (-5..0..5)
             -5 strong sell
             +5 strong buy
    """
    #TODO: jork: implement
    
    log.info ("Generate Trade Signal for product: "+market.product_id)
    
    signal = 0 
    
    ################# TODO: FIXME: jork: Implementation ###################
    
    return signal

def consume_trade_signal (market, signal):
    """
    Execute the trade based on signal 
     - Policy can be applied on the behavior of signal strength 
     Logic :-
     * Based on the Signal strength and fund balances, take trade decision and
        calculate the exact amount to be traded
         1.  See if there is any manual override, if there is one, that takes priority (skip other steps?)
         2.  el
         
         
        -- Manual Override file: "override/TRADE_<exchange_name>.<product>"
            Json format:
            {
             product : <ETH-USD|BTC-USD>
             type    : <BUY|SELL>
             size    : <BTC>
             price   : <limit-price>
            }
            
        -- To ignore a product
           add an empty file with name "<exchange_name>_<product>.ignore"
    """
    exchange_name = market.exchange.__name__
    ignore_file = "override/%s_%s.ignore"%(exchange_name, market.product_id)
    #Override file name = override/TRADE_<exchange_name>.<product>
    if (os.path.isfile(ignore_file)):
        log.info("Ignore file present for product. Skip processing! "+ignore_file)
        return
    #get manual trade reqs if any
    trade_req_list = get_manual_trade_req (market)
    # Now generate auto trade req list
    log.info ("Trade Signal strength:"+str(signal))         ## TODO: FIXME: IMPLEMENT:
    trade_req = generate_trade_request(market, signal)
    #validate the trade Req
    if (trade_req != None and trade_req.size > 0 and trade_req.price > 0):
        ## Now we have a valid trader request
        # Execute the trade request and retrieve the order # and store it
        trade_req_list.append(trade_req)
    if (len(trade_req_list)):
        execute_market_trade(market, trade_req_list)         
#EOF