#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
int main(void);

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata;) {
        *dst++ = *src++;
    }
    for (uint32_t *dst = &_sbss; dst < &_ebss;) {
        *dst++ = 0;
    }
    main();
    for (;;) {
    }
}

static void Default_Handler(void)
{
    for (;;) {
    }
}

void TIM1_UP_TIM10_IRQHandler(void);

/* 16 core exceptions + external IRQs up to TIM1_UP (IRQ 25). */
__attribute__((section(".isr_vector"), used))
const void *const vectors[16 + 26] = {
    [0] = &_estack,
    [1] = Reset_Handler,
    [2 ... 15] = Default_Handler,
    [16 ... 16 + 24] = Default_Handler,
    [16 + 25] = TIM1_UP_TIM10_IRQHandler,
};
