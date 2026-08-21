import unittest
from unittest.mock import patch

from interfaces.ICD4.icd4_drv import ICD4Driver, ICD4UsbIds
from interfaces.PK4.pk4_drv import PK4Driver, PK4UsbIds


class TestToolDriverLifecycle(unittest.TestCase):
    def test_pk4_context_manager_releases_transport(self):
        with patch("mchp_ri4.transport.PyusbTransport") as transport_type:
            with PK4Driver(PK4UsbIds(vid=0x04D8, pid=0x9012)):
                pass
        transport_type.return_value.close.assert_called_once_with()

    def test_icd4_close_releases_transport(self):
        with patch("mchp_ri4.transport.PyusbTransport") as transport_type:
            driver = ICD4Driver(ICD4UsbIds(vid=0x04D8, pid=0x9036))
            driver.close()
        transport_type.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
