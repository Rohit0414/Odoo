from odoo import api, fields, models

class StockDashboard(models.Model):
    _name = 'stock.dashboard'
    _description = 'Inventory Dashboard'

    name = fields.Char(default="Inventory Dashboard")
    total_inventory = fields.Float(
        string="Total Inventory",
        compute="_compute_inventory",
        store=False,
        help="Sum of quantities available for all products."
    )
    pending_orders = fields.Integer(
        string="Pending Orders",
        compute="_compute_pending_orders",
        store=False,
        help="Count of pending delivery orders."
    )

    @api.depends()
    def _compute_inventory(self):
        """
        Compute the total available inventory by summing all
        stock quant quantities.
        """
        quant_obj = self.env['stock.quant']
        # Example: summing up the 'quantity' field from all stock.quants
        total = sum(quant_obj.search([]).mapped('quantity'))
        self.total_inventory = total

    @api.depends()
    def _compute_pending_orders(self):
        """
        Compute the number of pending orders by counting
        stock pickings in a confirmed state.
        """
        picking_obj = self.env['stock.picking']
        pending = picking_obj.search_count([('state', '=', 'confirmed')])
        self.pending_orders = pending
