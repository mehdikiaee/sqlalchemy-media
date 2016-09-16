
import unittest
import functools
from io import BytesIO
import json
from os import makedirs
from os.path import join, dirname, abspath, exists

from sqlalchemy import Column, Integer, create_engine, Unicode, TypeDecorator
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy_media import MutableDictAttachment, StoreManager, FileSystemStore, UnboundAttachmentError


# noinspection PyAbstractClass
class Json(TypeDecorator):
    impl = Unicode

    def process_bind_param(self, value, engine):
        return json.dumps(value)

    def process_result_value(self, value, engine):
        if value is None:
            return None

        return json.loads(value)


class AttachmentTestCase(unittest.TestCase):

    def setUp(self):
        self.this_dir = abspath(dirname(__file__))
        self.stuff_path = join(self.this_dir, 'stuff')
        self.sample_text_file1 = join(self.stuff_path, 'sample_text_file1.txt')
        self.temp_path = join(self.this_dir, 'temp', 'test_attachment')
        if not exists(self.temp_path):
            makedirs(self.temp_path, exist_ok=True)

        StoreManager.register('fs', functools.partial(FileSystemStore, self.temp_path), default=True)

    def test_attachment(self):

        Base = declarative_base()

        engine = create_engine('sqlite:///:memory:', echo=True)
        # engine = create_engine('postgresql://postgres:postgres@localhost/deleteme_jsonb', echo=True)

        class Person(Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode(50), nullable=False, default='person1')
            image = Column(MutableDictAttachment.as_mutable(Json), default={'d': 'a'})

            def __repr__(self):
                return "<Person id=%s name=%s image=%s />" % (self.id, self.name, self.image)

        Base.metadata.create_all(engine, checkfirst=True)

        session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=True,
            twophase=False
        )

        session = session_factory()

        # person1 = Person(name='person1')
        person1 = Person()
        self.assertIsNone(person1.image)
        sample_content = b'Simple text.'
        person1.image = MutableDictAttachment()
        with StoreManager():
            self.assertRaises(
                UnboundAttachmentError,
                person1.image.attach,
                BytesIO(sample_content), content_type='text/plain', extension='.txt')

            session.add(person1)

            # First file before commit
            person1.image.attach(BytesIO(sample_content), content_type='text/plain', extension='.txt')
            self.assertIsInstance(person1.image, MutableDictAttachment)
            self.assertDictEqual(person1.image, {
                'contentType': 'text/plain',
                'key': person1.image.key,
                'extension': '.txt',
                'length': len(sample_content)
            })
            first_filename = join(self.temp_path, person1.image.path)
            self.assertTrue(exists(first_filename))

            # Second file before commit
            person1.image.attach(BytesIO(sample_content), content_type='text/plain', extension='.txt')
            second_filename = join(self.temp_path, person1.image.path)
            self.assertTrue(exists(second_filename))

            session.commit()
            self.assertFalse(exists(first_filename))
            self.assertTrue(exists(second_filename))

            # Loading again
            sample_content = b'Lorem ipsum dolor sit amet'
            person1 = session.query(Person).filter(Person.id == person1.id).one()
            person1.image.attach(BytesIO(sample_content), content_type='text/plain', extension='.txt')
            self.assertIsInstance(person1.image, MutableDictAttachment)
            self.assertDictEqual(person1.image, {
                'contentType': 'text/plain',
                'key': person1.image.key,
                'extension': '.txt',
                'length': len(sample_content)
            })
            third_filename = join(self.temp_path, person1.image.path)
            self.assertTrue(exists(second_filename))
            self.assertTrue(exists(third_filename))

            session.commit()
            self.assertFalse(exists(second_filename))
            self.assertTrue(exists(third_filename))

            # Rollback
            person1.image.attach(BytesIO(sample_content), content_type='text/plain', extension='.txt')
            forth_filename = person1.image.filename
            self.assertFalse(exists(forth_filename))
            session.rollback()
            self.assertTrue(exists(third_filename))
            self.assertFalse(exists(forth_filename))

# Empty content type
# mime & ext from url
# delete file after object deletion.

if __name__ == '__main__':
    unittest.main()


