`default_nettype none

module spi_peripheral (
    input  wire       clk,      // clock
    input  wire       rst_n,     // reset_n - low to reset
    input  wire [2:0]  ui_in,    // SCLK, COPI, nCS
    output  reg [7:0] en_reg_out_7_0,
    output  reg [7:0] en_reg_out_15_8,
    output  reg [7:0] en_reg_pwm_7_0,
    output  reg [7:0] en_reg_pwm_15_8,
    output  reg [7:0] pwm_duty_cycle
);
    localparam bit_per_transaction = 16; // 1 R/W, 7 address, 8 data bits
    reg[4:0] bit_counter;

    localparam max_address = 7'h04;

    reg[1:0] sync_sclk;
    reg sclk_delay;
    wire sclk_posedge;

    reg[1:0] sync_copi;

    reg[1:0] sync_ncs;
    reg ncs_delay;
    wire ncs_posedge;
    
    reg [7:0] internal_data_register;
    reg [6:0] internal_address_register;
    reg read_write;
        
    assign ncs_posedge = sync_ncs[1] && !ncs_delay;
    assign sclk_posedge = sync_sclk[1] && !sclk_delay;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sync_sclk <= 0;
            sync_copi <= 0;
            sync_ncs <= 2'b11;  // since sync_ncs is active low
            sclk_delay <= 0;
            ncs_delay <= 1;

            internal_data_register <= 0;
            internal_address_register <= 0;
            bit_counter <= 0;
            read_write <= 0;
            en_reg_out_7_0 <= 0;
            en_reg_out_15_8 <= 0;
            en_reg_pwm_7_0 <= 0;
            en_reg_pwm_15_8 <= 0;
            pwm_duty_cycle <= 0;
        end else begin
            // synchronization chains to stabilize sclk, copi and ncs
            sync_sclk[0] <= ui_in[0];
            sync_sclk[1] <= sync_sclk[0];
            sclk_delay <= sync_sclk[1];

            sync_copi[0] <= ui_in[1];
            sync_copi[1] <= sync_copi[0];
            
            sync_ncs[0] <= ui_in[2];
            sync_ncs[1] <= sync_ncs[0];
            ncs_delay <= sync_ncs[1];

            // read in data when nCS pulled low to signal transaction is in progress
            if (!sync_ncs[1]) begin
                if (sclk_posedge) begin
                    bit_counter <= bit_counter + 1;
                    if (bit_counter == 0) begin
                        read_write <= sync_copi[1];
                    end
                    if (bit_counter >= 1 && bit_counter <= 7) begin
                        internal_address_register <= {internal_address_register[5:0], sync_copi[1]};
                    end
                    if (read_write && bit_counter >= 8) begin
                        internal_data_register <= {internal_data_register[6:0], sync_copi[1]};
                    end
                end
            end

            // update registers after entire transaction is complete
            if (ncs_posedge) begin
                bit_counter <= 0;
                if (read_write && bit_counter == bit_per_transaction && internal_address_register <= max_address) begin
                    case (internal_address_register)
                        7'h00: en_reg_out_7_0 <= internal_data_register;
                        7'h01: en_reg_out_15_8 <= internal_data_register;
                        7'h02: en_reg_pwm_7_0 <= internal_data_register;
                        7'h03: en_reg_pwm_15_8 <= internal_data_register;
                        7'h04: pwm_duty_cycle <= internal_data_register;
                        default: begin end
                    endcase
                end
            end
        end
    end

endmodule
